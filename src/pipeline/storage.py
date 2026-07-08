"""知识库落盘：knowledge-base/videos/{bvid}[-pN]-{标题}/（目录结构见架构文档 §5）。"""

import json
import re
from pathlib import Path

from .models import Segment, Transcript, VideoRef

_UNSAFE_RE = re.compile(r'[\\/:*?"<>|\s]+')
_PARA_GAP_SEC = 2.5    # 相邻字幕段间隔超过该值则另起段落
_PARA_MAX_CHARS = 300  # 单段落最大字数


def _safe_name(name: str, max_len: int = 40) -> str:
    return _UNSAFE_RE.sub("-", name).strip("-")[:max_len] or "untitled"


def _fmt_ts(seconds: float) -> str:
    s = int(seconds)
    if s >= 3600:
        return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"
    return f"{s // 60:02d}:{s % 60:02d}"


def video_dir(kb_root: Path, video: VideoRef) -> Path:
    stem = video.bvid
    if video.total_parts > 1:
        stem += f"-p{video.part_no}"
    return kb_root / "videos" / f"{stem}-{_safe_name(video.title)}"


def _group_paragraphs(segments: list[Segment]) -> list[tuple[float, str]]:
    """把细碎字幕段合并成可读段落，返回 [(段落起始秒, 文本), ...]。"""
    paragraphs: list[tuple[float, str]] = []
    buf: list[str] = []
    start = 0.0
    prev_end = 0.0
    for seg in segments:
        if buf and (seg.start - prev_end > _PARA_GAP_SEC or sum(map(len, buf)) > _PARA_MAX_CHARS):
            paragraphs.append((start, "".join(buf)))
            buf = []
        if not buf:
            start = seg.start
        buf.append(seg.text)
        prev_end = seg.end
    if buf:
        paragraphs.append((start, "".join(buf)))
    return paragraphs


def render_markdown(video: VideoRef, transcript: Transcript) -> str:
    source_doc = {"cc": "人工 CC 字幕", "ai-subtitle": "B 站 AI 字幕", "whisper": "本地 whisper 转写"}
    title = video.title + (f"（P{video.part_no}: {video.part_title}）" if video.total_parts > 1 else "")
    lines = [
        f"# {title}",
        "",
        f"> 来源视频：<{video.url}> · UP 主：{video.up_name} · 时长：{_fmt_ts(video.duration_sec)}",
        f"> 逐字稿来源：{source_doc[transcript.source]}",
        "",
    ]
    for ts, text in _group_paragraphs(transcript.segments):
        lines.append(f"**[{_fmt_ts(ts)}]** {text}")
        lines.append("")
    return "\n".join(lines)


def save_transcript(kb_root: Path, video: VideoRef, transcript: Transcript) -> Path:
    """落盘 meta.json / transcript.json / transcript.md，返回视频目录。"""
    vdir = video_dir(kb_root, video)
    vdir.mkdir(parents=True, exist_ok=True)

    (vdir / "meta.json").write_text(
        video.model_dump_json(indent=2), encoding="utf-8"
    )
    (vdir / "transcript.json").write_text(
        transcript.model_dump_json(indent=2), encoding="utf-8"
    )
    (vdir / "transcript.md").write_text(render_markdown(video, transcript), encoding="utf-8")
    return vdir
