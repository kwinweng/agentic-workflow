"""飞书机器人：丢链接 → 受理回执 → 完成通知卡片（含 skill 草稿审核按钮）。

架构（见 docs/02-架构设计.md §3.5）：
- lark-oapi SDK **长连接模式**接收事件（无需公网回调地址），可选依赖 `.[feishu]`
- 业务逻辑（链接提取/事件去重/建任务/卡片构造）与 SDK 解耦，纯函数可测
- 与 worker 同进程部署：serve() 同时启动 ws 客户端与任务 worker

启动：python -m pipeline.feishu_bot
"""

import asyncio
import json
import logging
import re
from pathlib import Path

from . import db, service, skills_store
from .config import Settings, get_settings
from .db import init_db

logger = logging.getLogger(__name__)

_LINK_RE = re.compile(
    r"(https?://(?:www\.)?bilibili\.com/video/\S+"
    r"|https?://b23\.tv/\w+"
    r"|https?://space\.bilibili\.com/\d+/(?:lists/\d+\S*|channel/collectiondetail\?\S+)"
    r"|BV[0-9A-Za-z]{10})"
)

HELP_TEXT = (
    "把 B 站链接发给我即可自动生成逐字稿并提炼团队技能：\n"
    "支持 视频链接 / BV 号 / b23.tv 短链 / 合集链接，一条消息可含多个链接。"
)


def extract_bili_links(text: str) -> list[str]:
    """从消息文本提取 B 站链接（去重保序）。"""
    seen: dict[str, None] = {}
    for m in _LINK_RE.finditer(text or ""):
        seen.setdefault(m.group(1).rstrip('",;)】]'), None)
    return list(seen)


def is_duplicate_event(db_path: Path, event_id: str) -> bool:
    """事件去重：首次见到登记并返回 False，重复投递返回 True。"""
    if not event_id:
        return False
    with db.connect(db_path) as conn:
        try:
            conn.execute("INSERT INTO feishu_events (event_id) VALUES (?)", (event_id,))
            return False
        except Exception:  # PRIMARY KEY 冲突 → 重复事件
            return True


def handle_message(db_path: Path, event_id: str, chat_id: str, text: str) -> str | None:
    """处理一条飞书消息，返回应回复的文本；None 表示不回复（重复事件）。"""
    if is_duplicate_event(db_path, event_id):
        logger.info("重复事件已忽略: %s", event_id)
        return None
    links = extract_bili_links(text)
    if not links:
        return HELP_TEXT
    ids = service.create_tasks(
        db_path, links, source="feishu", options={"distill": True}, feishu_chat_id=chat_id
    )
    lines = [f"已受理 {len(ids)} 个任务，完成后我会在这里通知你："]
    lines += [f"  #{tid} {url}" for tid, url in zip(ids, links)]
    return "\n".join(lines)


# ---- 完成通知卡片 -----------------------------------------------------------

_SOURCE_DOC = {"cc": "人工 CC 字幕", "ai-subtitle": "B 站 AI 字幕", "whisper": "本地 whisper 转写"}


def build_done_card(db_path: Path, task: dict, result: dict) -> dict:
    """任务完成卡片：标题/来源/落盘路径/skill 草稿数 + 每个草稿的审核按钮。"""
    videos = result.get("videos", [])
    sources = "、".join(sorted({_SOURCE_DOC.get(v.get("source"), "?") for v in videos}))
    skills_info = result.get("skills") or {}

    elements: list[dict] = [{
        "tag": "div",
        "text": {"tag": "lark_md", "content": (
            f"**《{result.get('title', '?')}》** 处理完成 ✅\n"
            f"视频数：{result.get('video_count')} · 逐字稿来源：{sources}\n"
            f"落盘：{videos[0]['dir'] if videos else '?'}"
        )},
    }]

    if skills_info.get("skipped"):
        elements.append({"tag": "div", "text": {
            "tag": "lark_md", "content": f"⚠️ 知识提炼已跳过：{skills_info['skipped']}"}})
    for name in skills_info.get("names", []):
        row = next(
            (d for d in service.list_skill_drafts(db_path) if d["name"] == name), None
        )
        if row is None:
            continue
        elements.append({"tag": "div", "text": {
            "tag": "lark_md", "content": f"🧩 skill 草稿：**{row['title']}**（{name}）"}})
        elements.append({"tag": "action", "actions": [
            {"tag": "button", "text": {"tag": "plain_text", "content": "✅ 采纳"},
             "type": "primary",
             "value": {"action": "approve_skill", "skill_id": row["id"]}},
            {"tag": "button", "text": {"tag": "plain_text", "content": "↩ 退回"},
             "value": {"action": "reject_skill", "skill_id": row["id"]}},
        ]})

    return {
        "config": {"wide_screen_mode": True},
        "header": {"template": "green",
                   "title": {"tag": "plain_text", "content": "逐字稿任务完成"}},
        "elements": elements,
    }


def build_failed_text(task: dict) -> str:
    return f"任务 #{task['id']} 处理失败（已重试 {service.MAX_ATTEMPTS} 次）：{task['url']}\n请在管理后台查看错误详情并重试。"


def handle_card_action(db_path: Path, kb_root: Path, value: dict, operator: str) -> str:
    """卡片按钮回调：与后台审核队列同一状态机（skills_store）。"""
    skill_id = int(value.get("skill_id", 0))
    if value.get("action") == "approve_skill":
        ok = skills_store.approve_skill(db_path, kb_root, skill_id, reviewer=operator)
        return "已采纳，技能已入库 ✅" if ok else "该草稿已被处理过"
    if value.get("action") == "reject_skill":
        ok = skills_store.reject_skill(db_path, skill_id, reviewer=operator)
        return "已退回 ↩" if ok else "该草稿已被处理过"
    return "未知操作"


# ---- lark-oapi SDK 接线（仅在配置了飞书凭据时可用）---------------------------


def serve(settings: Settings | None = None) -> None:  # pragma: no cover - 需真实凭据
    """同进程启动：飞书长连接客户端 + 任务 worker（完成后回消息）。"""
    try:
        import lark_oapi as lark
    except ImportError as e:
        raise RuntimeError("未安装 lark-oapi，安装：pip install '.[feishu]'") from e

    settings = settings or get_settings()
    if not (settings.feishu_app_id and settings.feishu_app_secret):
        raise RuntimeError("未配置 FEISHU_APP_ID / FEISHU_APP_SECRET")
    init_db(settings.db_path).close()

    lark_client = lark.Client.builder() \
        .app_id(settings.feishu_app_id).app_secret(settings.feishu_app_secret).build()

    def _reply_text(chat_id: str, text: str) -> None:
        from lark_oapi.api.im.v1 import CreateMessageRequest, CreateMessageRequestBody
        req = CreateMessageRequest.builder().receive_id_type("chat_id").request_body(
            CreateMessageRequestBody.builder()
            .receive_id(chat_id).msg_type("text")
            .content(json.dumps({"text": text}, ensure_ascii=False)).build()
        ).build()
        lark_client.im.v1.message.create(req)

    def _reply_card(chat_id: str, card: dict) -> None:
        from lark_oapi.api.im.v1 import CreateMessageRequest, CreateMessageRequestBody
        req = CreateMessageRequest.builder().receive_id_type("chat_id").request_body(
            CreateMessageRequestBody.builder()
            .receive_id(chat_id).msg_type("interactive")
            .content(json.dumps(card, ensure_ascii=False)).build()
        ).build()
        lark_client.im.v1.message.create(req)

    def on_message(event) -> None:
        msg = event.event.message
        if msg.message_type != "text":
            return
        text = json.loads(msg.content).get("text", "")
        reply = handle_message(
            settings.db_path, event.header.event_id, msg.chat_id, text
        )
        if reply:
            _reply_text(msg.chat_id, reply)

    def on_card(event):
        value = event.event.action.value or {}
        operator = event.event.operator.open_id or "feishu-user"
        toast = handle_card_action(settings.db_path, settings.kb_root, value, operator)
        import lark_oapi as lark_
        return lark_.event.callback.model.P2CardActionTriggerResponse(
            {"toast": {"type": "info", "content": toast}}
        )

    handler = lark.EventDispatcherHandler.builder("", "") \
        .register_p2_im_message_receive_v1(on_message) \
        .register_p2_card_action_trigger(on_card) \
        .build()
    ws_client = lark.ws.Client(
        settings.feishu_app_id, settings.feishu_app_secret,
        event_handler=handler, log_level=lark.LogLevel.INFO,
    )

    def notifier(task: dict, result: dict | None, outcome: str) -> None:
        # 非飞书来源（后台提交）的任务，失败/完成通知发到告警群（若配置）
        chat_id = task.get("feishu_chat_id") or settings.feishu_alert_chat_id
        if not chat_id:
            return
        if outcome == "done" and result is not None:
            _reply_card(chat_id, build_done_card(settings.db_path, task, result))
        elif outcome == "failed":
            _reply_text(chat_id, build_failed_text(task))

    async def main() -> None:
        from .worker import worker_loop
        await asyncio.gather(
            asyncio.to_thread(ws_client.start),
            worker_loop(settings, notifier=notifier),
        )

    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())


if __name__ == "__main__":  # pragma: no cover
    serve()
