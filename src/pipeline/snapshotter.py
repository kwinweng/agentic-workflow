"""图文稿生成：下载视频流 + ffmpeg 按段落时间戳抽帧 → article.md（架构文档 §3.3）。

仅当任务开启 options.article 时执行（需要额外下载视频流，成本高于纯逐字稿）。
抽帧策略：以逐字稿段落起点为候选，稀释到最小间隔 frame_min_gap 秒一张。
"""

import logging
import subprocess
from pathlib import Path
from typing import Callable

from .models import Transcript, VideoRef
from .storage import _fmt_ts, _group_paragraphs, video_dir
from .transcriber.downloader import DownloadError

logger = logging.getLogger(__name__)

FRAME_MIN_GAP_SEC = 60.0

# (video_path, timestamp_sec, out_path) -> None
FrameExtractor = Callable[[Path, float, Path], None]


def select_frame_timestamps(
    paragraph_starts: list[float], min_gap: float = FRAME_MIN_GAP_SEC
) -> list[float]:
    """段落起点稀释为抽帧时间点：保证相邻两张至少间隔 min_gap 秒。"""
    selected: list[float] = []
    for ts in sorted(paragraph_starts):
        if not selected or ts - selected[-1] >= min_gap:
            selected.append(ts)
    return selected


def download_video(video: VideoRef, work_dir: Path, tool: str = "bbdown") -> Path:
    """下载完整视频（含画面），供抽帧用。"""
    out_dir = work_dir / video.bvid
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{video.bvid}_p{video.part_no}_video"

    if tool == "bbdown":
        cmd = ["BBDown", video.url or f"https://www.bilibili.com/video/{video.bvid}",
               "-p", str(video.part_no), "--work-dir", str(out_dir), "--file-pattern", stem]
    elif tool == "yt-dlp":
        cmd = ["yt-dlp", "-f", "bv*+ba/b", "-o", str(out_dir / f"{stem}.%(ext)s"),
               "--playlist-items", str(video.part_no),
               video.url or f"https://www.bilibili.com/video/{video.bvid}"]
    else:
        raise ValueError(f"未知下载工具: {tool}")

    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    if proc.returncode != 0:
        raise DownloadError(f"{tool} 视频下载失败 (exit {proc.returncode}): {proc.stderr[-500:]}")

    candidates = sorted(
        (p for p in out_dir.glob(f"{stem}*") if p.suffix in {".mp4", ".mkv", ".flv", ".webm"}),
        key=lambda p: p.stat().st_size, reverse=True,
    )
    if not candidates:
        raise DownloadError(f"{tool} 执行成功但未找到视频产物: {out_dir}/{stem}*")
    return candidates[0]


def ffmpeg_extract_frame(video_path: Path, timestamp: float, out_path: Path) -> None:
    proc = subprocess.run(
        ["ffmpeg", "-y", "-ss", f"{timestamp:.2f}", "-i", str(video_path),
         "-frames:v", "1", "-q:v", "3", str(out_path)],
        capture_output=True, text=True, timeout=120,
    )
    if proc.returncode != 0 or not out_path.exists():
        raise RuntimeError(f"ffmpeg 抽帧失败 @{timestamp:.0f}s: {proc.stderr[-300:]}")


def render_article(
    video: VideoRef, transcript: Transcript, images: dict[float, str]
) -> str:
    """图文稿：逐字稿段落 + 就近插入的关键帧截图（相对路径引用 images/）。"""
    title = video.title + (f"（P{video.part_no}: {video.part_title}）" if video.total_parts > 1 else "")
    lines = [
        f"# {title} · 图文稿",
        "",
        f"> 来源视频：<{video.url}> · UP 主：{video.up_name}",
        "",
    ]
    for ts, text in _group_paragraphs(transcript.segments):
        if ts in images:
            lines.append(f"![{_fmt_ts(ts)}]({images[ts]})")
            lines.append("")
        lines.append(f"**[{_fmt_ts(ts)}]** {text}")
        lines.append("")
    return "\n".join(lines)


def build_article(
    video: VideoRef,
    transcript: Transcript,
    kb_root: Path,
    work_dir: Path,
    *,
    downloader: str = "bbdown",
    frame_extractor: FrameExtractor = ffmpeg_extract_frame,
    video_downloader: Callable[[VideoRef, Path, str], Path] = download_video,
    min_gap: float = FRAME_MIN_GAP_SEC,
) -> tuple[Path, int]:
    """生成图文稿，返回 (article.md 路径, 截图数)。抽帧失败的时间点跳过，不阻塞整篇。"""
    vdir = video_dir(kb_root, video)
    img_dir = vdir / "images"
    img_dir.mkdir(parents=True, exist_ok=True)

    paragraphs = _group_paragraphs(transcript.segments)
    timestamps = select_frame_timestamps([ts for ts, _ in paragraphs], min_gap)

    video_path = video_downloader(video, work_dir, downloader)
    images: dict[float, str] = {}
    for i, ts in enumerate(timestamps, 1):
        out = img_dir / f"{i:04d}_{_fmt_ts(ts).replace(':', '-')}.jpg"
        try:
            frame_extractor(video_path, ts, out)
            images[ts] = f"images/{out.name}"
        except Exception:
            logger.warning("%s: 抽帧失败 @%.0fs，跳过", video.bvid, ts, exc_info=True)

    article = vdir / "article.md"
    article.write_text(render_article(video, transcript, images), encoding="utf-8")
    logger.info("%s p%s: 图文稿完成，%d 张截图", video.bvid, video.part_no, len(images))
    return article, len(images)
