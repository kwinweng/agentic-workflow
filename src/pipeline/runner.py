"""单任务执行器：一条 URL → 解析 → 逐字稿 → 落盘（→ 可选 AI 提炼）→ 登记。

被 worker 在线程池里调用（内部全是同步代码）。
"""

import json
import logging
from pathlib import Path

from .bili_client import BiliClient
from .config import Settings
from .distiller import distill_video
from .llm import ChatLLM, OpenAICompatLLM
from .resolver import resolve
from .service import add_skill, add_transcript, set_task_status
from .storage import render_markdown, save_transcript
from .transcriber import get_transcript
from .transcriber.asr import AsrEngine, create_engine

logger = logging.getLogger(__name__)

_asr_engine: AsrEngine | None = None


def _get_asr_engine(settings: Settings) -> AsrEngine:
    global _asr_engine
    if _asr_engine is None:
        _asr_engine = create_engine(
            "faster-whisper",
            model_size=settings.whisper_model,
            device=settings.whisper_device,
        )
    return _asr_engine


def _build_llm(settings: Settings) -> ChatLLM:
    return OpenAICompatLLM(settings.llm_base_url, settings.llm_api_key, settings.llm_model)


def run_task(task: dict, settings: Settings, *, llm: ChatLLM | None = None) -> dict:
    """执行任务，返回结果摘要 dict；失败抛异常由 worker 记录。

    options.distill=true 时在转写后追加 AI 提炼（清洗稿 + skill 草稿入审核队列）。
    """
    options = json.loads(task.get("options_json") or "{}")
    client = BiliClient(settings.bili_sessdata, settings.bili_min_interval)
    try:
        videos = resolve(task["url"], client)
        if not videos:
            raise RuntimeError("链接未解析出任何视频")

        outputs = []
        transcripts = []
        for video in videos:
            transcript = get_transcript(
                client, video,
                asr_engine=_get_asr_engine(settings),
                work_dir=settings.work_dir,
                downloader=settings.downloader,
            )
            vdir = save_transcript(settings.kb_root, video, transcript)
            add_transcript(
                settings.db_path, task["id"], transcript.source,
                str(vdir / "transcript.json"), str(vdir / "transcript.md"),
                video.duration_sec,
            )
            transcripts.append((video, transcript))
            outputs.append({
                "bvid": video.bvid, "part_no": video.part_no,
                "title": video.title, "source": transcript.source,
                "dir": str(vdir),
            })

        result: dict = {
            "video_count": len(outputs),
            "videos": outputs,
            "bvid": outputs[0]["bvid"],
            "title": outputs[0]["title"],
        }

        if options.get("distill"):
            result["skills"] = _distill_all(task, settings, transcripts, llm)
        return result
    finally:
        client.close()


def _distill_all(task: dict, settings: Settings, transcripts: list, llm: ChatLLM | None) -> dict:
    """AI 提炼步骤。LLM 未配置时跳过并在结果中说明，不让整个任务失败。"""
    if llm is None:
        if not settings.llm_api_key:
            logger.warning("任务 #%s 要求提炼但未配置 LLM_API_KEY，跳过", task["id"])
            return {"skipped": "未配置 LLM_API_KEY"}
        llm = _build_llm(settings)

    set_task_status(settings.db_path, task["id"], "distilling")
    skill_names: list[str] = []
    for video, transcript in transcripts:
        drafts = distill_video(llm, settings, video, render_markdown(video, transcript))
        for draft, path in drafts:
            add_skill(settings.db_path, task["id"], draft.name, draft.title, str(path))
            skill_names.append(draft.name)
    return {"draft_count": len(skill_names), "names": skill_names}
