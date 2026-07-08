import pytest

from _samples import VIDEO
from pipeline import service
from pipeline.db import init_db
from pipeline.distiller import SkillDraft, render_skill_md
from pipeline.feishu_bot import (
    HELP_TEXT, build_done_card, build_failed_text, extract_bili_links,
    handle_card_action, handle_message, is_duplicate_event,
)


@pytest.fixture
def db_path(tmp_path):
    p = tmp_path / "f.db"
    init_db(p).close()
    return p


def test_extract_links_various_forms():
    text = (
        "看看这两个：https://www.bilibili.com/video/BV1GJ411x7h7?p=2 和 "
        "https://b23.tv/abc123，还有裸号 BV1xx411c7XX，"
        "合集 https://space.bilibili.com/123/lists/456?type=season"
    )
    links = extract_bili_links(text)
    assert len(links) == 4
    assert links[0].startswith("https://www.bilibili.com/video/")
    assert "BV1xx411c7XX" in links


def test_extract_links_dedup_and_empty():
    assert extract_bili_links("BV1xx411c7XX BV1xx411c7XX") == ["BV1xx411c7XX"]
    assert extract_bili_links("你好，帮我处理一下") == []
    assert extract_bili_links("") == []


def test_event_dedup(db_path):
    assert not is_duplicate_event(db_path, "evt-1")
    assert is_duplicate_event(db_path, "evt-1")
    assert not is_duplicate_event(db_path, "evt-2")
    assert not is_duplicate_event(db_path, "")  # 无 event_id 不去重


def test_handle_message_creates_feishu_tasks(db_path):
    reply = handle_message(db_path, "evt-a", "chat-1", "学习 BV1xx411c7XX")
    assert "已受理 1 个任务" in reply
    [task] = service.list_tasks(db_path)
    assert task["source"] == "feishu"
    assert task["feishu_chat_id"] == "chat-1"
    assert '"distill": true' in task["options_json"]


def test_handle_message_help_and_duplicate(db_path):
    assert handle_message(db_path, "evt-b", "chat-1", "在吗") == HELP_TEXT
    assert handle_message(db_path, "evt-b", "chat-1", "在吗") is None  # 重复投递


def _make_draft(db_path, kb_root, task_id, name="test-skill"):
    d = SkillDraft(name=name, title="测试技能", description="当…时使用", body="正文")
    ddir = kb_root / "drafts" / name
    ddir.mkdir(parents=True)
    (ddir / "SKILL.md").write_text(render_skill_md(d, VIDEO), encoding="utf-8")
    return service.add_skill(db_path, task_id, name, d.title, str(ddir / "SKILL.md"))


def test_build_done_card_includes_skills_and_buttons(db_path, tmp_path):
    [tid] = service.create_tasks(db_path, ["BV1xx411c7XX"])
    sid = _make_draft(db_path, tmp_path / "kb", tid)
    task = {"id": tid, "feishu_chat_id": "chat-1"}
    result = {
        "title": "课程", "video_count": 1,
        "videos": [{"source": "cc", "dir": "/kb/videos/x"}],
        "skills": {"draft_count": 1, "names": ["test-skill"]},
    }
    card = build_done_card(db_path, task, result)
    text = str(card)
    assert "课程" in text and "人工 CC 字幕" in text and "测试技能" in text
    buttons = [e for e in card["elements"] if e.get("tag") == "action"]
    assert buttons[0]["actions"][0]["value"] == {"action": "approve_skill", "skill_id": sid}


def test_build_done_card_shows_skip_reason(db_path):
    card = build_done_card(db_path, {"id": 1}, {
        "title": "t", "video_count": 1, "videos": [{"source": "cc", "dir": "/x"}],
        "skills": {"skipped": "未配置 LLM_API_KEY"},
    })
    assert "未配置 LLM_API_KEY" in str(card)


def test_handle_card_action_approve_and_repeat(db_path, tmp_path):
    kb_root = tmp_path / "kb"
    [tid] = service.create_tasks(db_path, ["BV1xx411c7XX"])
    sid = _make_draft(db_path, kb_root, tid)

    toast = handle_card_action(db_path, kb_root, {"action": "approve_skill", "skill_id": sid}, "user-x")
    assert "已采纳" in toast
    assert (kb_root / "skills" / "test-skill" / "SKILL.md").exists()

    toast2 = handle_card_action(db_path, kb_root, {"action": "approve_skill", "skill_id": sid}, "user-x")
    assert "已被处理过" in toast2


def test_build_failed_text_mentions_task():
    text = build_failed_text({"id": 7, "url": "BV1xx411c7XX"})
    assert "#7" in text and "BV1xx411c7XX" in text
