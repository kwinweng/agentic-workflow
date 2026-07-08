"""逐字稿获取编排：字幕直抓优先，ASR 兜底（架构文档 §3.2）。"""

import logging
from pathlib import Path

from ..bili_client import BiliClient
from ..models import Transcript, VideoRef
from . import subtitle
from .asr import AsrEngine
from .downloader import download_audio

logger = logging.getLogger(__name__)


def get_transcript(
    client: BiliClient,
    video: VideoRef,
    *,
    asr_engine: AsrEngine | None = None,
    work_dir: Path = Path("./data/work"),
    downloader: str = "bbdown",
    allow_asr_fallback: bool = True,
) -> Transcript:
    # 路线 A：现成字幕。接口失败不阻塞任务，自动降级到 ASR。
    try:
        transcript = subtitle.fetch_transcript(client, video)
        if transcript is not None:
            logger.info("%s p%s: 使用现成字幕 (%s)", video.bvid, video.part_no, transcript.source)
            return transcript
        logger.info("%s p%s: 无可用字幕", video.bvid, video.part_no)
    except Exception:
        logger.warning("%s p%s: 字幕抓取失败，降级 ASR", video.bvid, video.part_no, exc_info=True)

    # 路线 B：下载音频 + 本地 ASR
    if not allow_asr_fallback:
        raise RuntimeError(f"{video.bvid} p{video.part_no}: 无字幕且已禁用 ASR 兜底")
    if asr_engine is None:
        raise RuntimeError(f"{video.bvid} p{video.part_no}: 无字幕且未配置 ASR 引擎")

    audio = download_audio(video, work_dir, tool=downloader)
    logger.info("%s p%s: 音频已下载 %s，开始 ASR 转写", video.bvid, video.part_no, audio.name)
    language, segments = asr_engine.transcribe(audio)
    if not segments:
        raise RuntimeError(f"{video.bvid} p{video.part_no}: ASR 转写结果为空")
    return Transcript(source="whisper", language=language, segments=segments)
