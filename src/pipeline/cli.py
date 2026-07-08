"""M1 CLI 批量入口。

用法：
    python -m pipeline.cli <url|BV号> [<url> ...]
    python -m pipeline.cli --no-asr BV1xxxxxxxxx   # 只走字幕直抓，不做 ASR 兜底
"""

import argparse
import logging
import sys

from .bili_client import BiliClient
from .config import get_settings
from .models import VideoRef
from .resolver import resolve
from .storage import save_transcript
from .transcriber import get_transcript
from .transcriber.asr import create_engine

logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pipeline.cli", description="B 站链接 → 逐字稿")
    parser.add_argument("urls", nargs="+", help="B 站链接 / BV 号 / b23.tv 短链 / 合集链接")
    parser.add_argument("--no-asr", action="store_true", help="禁用 ASR 兜底（无字幕即失败）")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    settings = get_settings()
    if not settings.bili_sessdata:
        logger.warning("未配置 BILI_SESSDATA，AI 字幕大概率抓取不到，将更依赖 ASR 兜底")

    client = BiliClient(settings.bili_sessdata, settings.bili_min_interval)
    asr_engine = None if args.no_asr else create_engine(
        "faster-whisper", model_size=settings.whisper_model, device=settings.whisper_device
    )

    videos: list[VideoRef] = []
    failed_links: list[str] = []
    for url in args.urls:
        try:
            videos.extend(resolve(url, client))
        except Exception as e:
            logger.error("链接解析失败 %s: %s", url, e)
            failed_links.append(url)

    ok, failed = 0, 0
    for video in videos:
        label = f"{video.bvid} p{video.part_no}/{video.total_parts}《{video.title}》"
        try:
            transcript = get_transcript(
                client, video,
                asr_engine=asr_engine,
                work_dir=settings.work_dir,
                downloader=settings.downloader,
                allow_asr_fallback=not args.no_asr,
            )
            out = save_transcript(settings.kb_root, video, transcript)
            print(f"✅ {label} → {out / 'transcript.md'}（来源：{transcript.source}）")
            ok += 1
        except Exception as e:
            logger.error("转写失败 %s: %s", label, e)
            failed += 1

    client.close()
    print(f"\n完成：{ok} 成功，{failed} 失败，{len(failed_links)} 条链接无法解析")
    return 0 if ok > 0 and failed == 0 and not failed_links else 1


if __name__ == "__main__":
    sys.exit(main())
