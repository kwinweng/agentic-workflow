"""transcriber 路线 A：B 站现成字幕 → Transcript。"""

from ..bili_client import BiliClient
from ..models import Segment, Transcript, VideoRef


def pick_best_subtitle(subtitles: list[dict]) -> dict | None:
    """选择最佳字幕：人工 CC 字幕 > AI 生成字幕（lan 以 ai- 开头）；中文优先。"""
    if not subtitles:
        return None
    usable = [s for s in subtitles if s.get("subtitle_url")]
    if not usable:
        return None

    def rank(s: dict) -> tuple:
        lan = s.get("lan", "")
        is_ai = lan.startswith("ai-")
        is_zh = "zh" in lan
        return (is_ai, not is_zh)  # False 排前面

    return sorted(usable, key=rank)[0]


def body_to_segments(body: list[dict]) -> list[Segment]:
    return [
        Segment(start=item.get("from", 0.0), end=item.get("to", 0.0), text=item.get("content", "").strip())
        for item in body
        if item.get("content", "").strip()
    ]


def fetch_transcript(client: BiliClient, video: VideoRef) -> Transcript | None:
    """尝试用现成字幕生成逐字稿；无可用字幕返回 None（由上层落到 ASR 兜底）。"""
    subtitles = client.list_subtitles(video.aid, video.cid)
    best = pick_best_subtitle(subtitles)
    if best is None:
        return None
    body = client.fetch_subtitle_body(best["subtitle_url"])
    segments = body_to_segments(body)
    if not segments:
        return None
    lan = best.get("lan", "zh")
    return Transcript(
        source="ai-subtitle" if lan.startswith("ai-") else "cc",
        language="zh" if "zh" in lan else lan,
        segments=segments,
    )
