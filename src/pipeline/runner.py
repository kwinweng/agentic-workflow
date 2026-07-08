"""单任务执行器：一条 URL → 解析 → 逐字稿 → 落盘 → 登记 transcripts。

被 worker 在线程池里调用（内部全是同步代码）。
"""

import logging
from pathlib import Path

from .bili_client import BiliClient
from .config import Settings
from .resolver import resolve
from .service import add_transcript
from .storage import save_transcript
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


def run_task(task: dict, settings: Settings) -> dict:
    """执行任务，返回结果摘要 dict；失败抛异常由 worker 记录。"""
    client = BiliClient(settings.bili_sessdata, settings.bili_min_interval)
    try:
        videos = resolve(task["url"], client)
        if not videos:
            raise RuntimeError("链接未解析出任何视频")

        outputs = []
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
            outputs.append({
                "bvid": video.bvid, "part_no": video.part_no,
                "title": video.title, "source": transcript.source,
                "dir": str(vdir),
            })
        return {
            "video_count": len(outputs),
            "videos": outputs,
            "bvid": outputs[0]["bvid"],
            "title": outputs[0]["title"],
        }
    finally:
        client.close()
