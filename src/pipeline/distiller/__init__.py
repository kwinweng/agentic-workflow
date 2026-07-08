"""AI 知识提炼：清洗稿 → Agent Skill 草稿（drafts 区，待人工审核）。

流程与格式以 docs/superpowers/specs/2026-07-08-knowledge-skills-design.md 为准。
"""

import json
import logging
import re
from pathlib import Path

from pydantic import BaseModel, field_validator

from ..config import Settings
from ..llm import ChatLLM, chunk_text
from ..models import Transcript, VideoRef
from ..storage import video_dir
from . import prompts

logger = logging.getLogger(__name__)

_VALID_CATEGORIES = {"工程实践", "架构模式", "工具链", "流程方法", "避坑"}
_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,60}$")


class SkillDraft(BaseModel):
    name: str
    title: str
    description: str
    category: str = "工程实践"
    confidence: str = "medium"
    body: str

    @field_validator("name")
    @classmethod
    def _name_slug(cls, v: str) -> str:
        v = v.strip().lower().replace("_", "-").replace(" ", "-")
        if not _NAME_RE.match(v):
            raise ValueError(f"非法 skill name: {v}")
        return v

    @field_validator("category")
    @classmethod
    def _category(cls, v: str) -> str:
        return v if v in _VALID_CATEGORIES else "工程实践"

    @field_validator("confidence")
    @classmethod
    def _confidence(cls, v: str) -> str:
        return v if v in {"high", "medium", "low"} else "medium"


def clean_transcript(llm: ChatLLM, transcript_md: str) -> str:
    """第一段：逐字稿 → 书面化整理稿（分块 map 后拼接）。"""
    parts = [
        llm.chat(prompts.CLEAN_SYSTEM, chunk)
        for chunk in chunk_text(transcript_md)
    ]
    return "\n\n".join(p.strip() for p in parts if p.strip())


def _parse_json_array(raw: str) -> list[dict]:
    """容错解析 LLM 输出的 JSON 数组（允许 ```json 围栏与前后杂讯）。"""
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?|```$", "", text, flags=re.MULTILINE).strip()
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end <= start:
        raise ValueError(f"LLM 输出中找不到 JSON 数组: {raw[:200]}")
    return json.loads(text[start : end + 1])


def extract_skill_drafts(
    llm: ChatLLM, cleaned_md: str, project_context: str, video: VideoRef
) -> list[SkillDraft]:
    """第二段：整理稿 + 项目背景 → skill 草稿列表（可为空）。"""
    user = (
        f"## 团队项目背景\n\n{project_context}\n\n"
        f"## 视频信息\n\n《{video.title}》 UP主：{video.up_name} 链接：{video.url}\n\n"
        f"## 整理稿\n\n{cleaned_md}"
    )
    raw = llm.chat(prompts.EXTRACT_SYSTEM, user)
    drafts: list[SkillDraft] = []
    for item in _parse_json_array(raw):
        try:
            drafts.append(SkillDraft(**item))
        except Exception:
            logger.warning("丢弃一条非法 skill 草稿: %s", str(item)[:200], exc_info=True)
    return drafts


def render_skill_md(draft: SkillDraft, video: VideoRef, status: str = "draft") -> str:
    return "\n".join([
        "---",
        f"name: {draft.name}",
        f"description: {draft.description}",
        f"category: {draft.category}",
        f"confidence: {draft.confidence}",
        f"source: {video.bvid}《{video.title}》 {video.url}",
        f"status: {status}",
        "---",
        "",
        f"# {draft.title}",
        "",
        draft.body.strip(),
        "",
    ])


def load_project_context(settings: Settings) -> str:
    f = settings.project_context_file
    if f.exists() and f.read_text(encoding="utf-8").strip():
        return f.read_text(encoding="utf-8").strip()
    return prompts.DEFAULT_PROJECT_CONTEXT


def distill_video(
    llm: ChatLLM, settings: Settings, video: VideoRef, transcript_md: str
) -> list[tuple[SkillDraft, Path]]:
    """整条提炼链路：清洗稿落盘 + skill 草稿写入 drafts 区。返回 (草稿, 文件路径) 列表。"""
    cleaned = clean_transcript(llm, transcript_md)
    vdir = video_dir(settings.kb_root, video)
    vdir.mkdir(parents=True, exist_ok=True)
    (vdir / "cleaned.md").write_text(cleaned, encoding="utf-8")

    drafts = extract_skill_drafts(llm, cleaned, load_project_context(settings), video)
    results: list[tuple[SkillDraft, Path]] = []
    for draft in drafts:
        ddir = settings.kb_root / "drafts" / draft.name
        ddir.mkdir(parents=True, exist_ok=True)
        path = ddir / "SKILL.md"
        path.write_text(render_skill_md(draft, video), encoding="utf-8")
        results.append((draft, path))
    logger.info("%s: 清洗稿 %d 字，产出 %d 个 skill 草稿", video.bvid, len(cleaned), len(drafts))
    return results
