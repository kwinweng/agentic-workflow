"""ASR 兜底前置：仅下载音频流（省带宽/磁盘，见架构文档 §3.2）。

工具可配置：BBDown（B 站专用，首选）或 yt-dlp（通用备选）。
两者都需在部署环境预装（M5 的 Docker 镜像会内置）。
"""

import subprocess
from pathlib import Path

from ..models import VideoRef


class DownloadError(RuntimeError):
    pass


def download_audio(video: VideoRef, work_dir: Path, tool: str = "bbdown") -> Path:
    out_dir = work_dir / video.bvid
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{video.bvid}_p{video.part_no}"

    if tool == "bbdown":
        cmd = [
            "BBDown", video.url or f"https://www.bilibili.com/video/{video.bvid}",
            "--audio-only",
            "-p", str(video.part_no),
            "--work-dir", str(out_dir),
            "--file-pattern", stem,
        ]
    elif tool == "yt-dlp":
        cmd = [
            "yt-dlp", "-f", "ba", "-x", "--audio-format", "m4a",
            "-o", str(out_dir / f"{stem}.%(ext)s"),
            "--playlist-items", str(video.part_no),
            video.url or f"https://www.bilibili.com/video/{video.bvid}",
        ]
    else:
        raise ValueError(f"未知下载工具: {tool}")

    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    if proc.returncode != 0:
        raise DownloadError(
            f"{tool} 下载失败 (exit {proc.returncode}): {proc.stderr[-500:]}"
        )

    candidates = sorted(
        (p for p in out_dir.glob(f"{stem}*") if p.suffix in {".m4a", ".mp3", ".aac", ".flac", ".wav"}),
        key=lambda p: p.stat().st_size,
        reverse=True,
    )
    if not candidates:
        raise DownloadError(f"{tool} 执行成功但未找到音频产物: {out_dir}/{stem}*")
    return candidates[0]
