import json

import pytest

from _samples import TRANSCRIPT, VIDEO
from pipeline import service
from pipeline.config import Settings
from pipeline.db import init_db
from pipeline.distiller import (
    SkillDraft, _parse_json_array, clean_transcript, distill_video, extract_skill_drafts,
)
from pipeline.storage import render_markdown

GOOD_SKILL = {
    "name": "API-Rate_Limit design",  # 故意脏格式，验证归一化
    "title": "接口限频设计",
    "description": "当需要调用有风控的第三方接口时使用本技能",
    "category": "工程实践",
    "confidence": "high",
    "body": "1. 最小间隔+抖动 [03:12]\n2. 失败降级",
}


class FakeLLM:
    """第一次调用（清洗）返回整理稿；第二次调用（提炼）返回 JSON。"""

    def __init__(self, extract_response: str):
        self.extract_response = extract_response
        self.calls: list[str] = []

    def chat(self, system: str, user: str) -> str:
        self.calls.append(system[:20])
        if "编辑" in system:  # CLEAN_SYSTEM
            return "## 整理稿\n\n[00:00] 核心内容"
        return self.extract_response


def test_parse_json_array_with_fences_and_noise():
    raw = "好的，以下是结果：\n```json\n[{\"a\": 1}]\n```\n希望有帮助"
    assert _parse_json_array(raw) == [{"a": 1}]


def test_parse_json_array_rejects_no_array():
    with pytest.raises(ValueError):
        _parse_json_array("没有数组")


def test_skill_draft_normalizes_fields():
    d = SkillDraft(**GOOD_SKILL)
    assert d.name == "api-rate-limit-design"
    assert d.category == "工程实践"
    d2 = SkillDraft(**{**GOOD_SKILL, "category": "乱写", "confidence": "超高"})
    assert d2.category == "工程实践"
    assert d2.confidence == "medium"


def test_extract_drops_invalid_items():
    llm = FakeLLM(json.dumps([GOOD_SKILL, {"name": "!!!", "title": "x"}], ensure_ascii=False))
    drafts = extract_skill_drafts(llm, "整理稿", "项目背景", VIDEO)
    assert len(drafts) == 1


def test_clean_transcript_joins_chunks():
    llm = FakeLLM("[]")
    cleaned = clean_transcript(llm, "原始逐字稿")
    assert "整理稿" in cleaned


def test_distill_video_writes_cleaned_and_drafts(tmp_path):
    settings = Settings(kb_root=tmp_path / "kb", db_path=tmp_path / "d.db")
    llm = FakeLLM(json.dumps([GOOD_SKILL], ensure_ascii=False))
    results = distill_video(llm, settings, VIDEO, render_markdown(VIDEO, TRANSCRIPT))

    assert len(results) == 1
    draft, path = results[0]
    assert path == settings.kb_root / "drafts" / "api-rate-limit-design" / "SKILL.md"
    content = path.read_text(encoding="utf-8")
    assert "status: draft" in content
    assert "name: api-rate-limit-design" in content
    assert VIDEO.bvid in content              # 溯源
    assert "[03:12]" in content               # 时间戳保留
    # 清洗稿落盘在视频目录
    cleaned_files = list((settings.kb_root / "videos").glob("*/cleaned.md"))
    assert len(cleaned_files) == 1


def test_distill_video_empty_extraction_ok(tmp_path):
    settings = Settings(kb_root=tmp_path / "kb", db_path=tmp_path / "d.db")
    llm = FakeLLM("[]")
    assert distill_video(llm, settings, VIDEO, "稿") == []
