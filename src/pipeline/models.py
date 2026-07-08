from typing import Literal

from pydantic import BaseModel

TranscriptSource = Literal["cc", "ai-subtitle", "whisper"]


class VideoRef(BaseModel):
    """一个可转写的最小单元：单个视频或多 P 视频的一个分 P。"""

    bvid: str
    aid: int
    cid: int
    part_no: int = 1          # 分 P 序号，从 1 开始
    total_parts: int = 1
    title: str                # 视频标题
    part_title: str = ""      # 分 P 标题（单 P 视频为空）
    duration_sec: int = 0
    up_name: str = ""
    url: str = ""


class Segment(BaseModel):
    start: float  # 秒
    end: float
    text: str


class Transcript(BaseModel):
    source: TranscriptSource
    language: str = "zh"
    segments: list[Segment]

    @property
    def full_text(self) -> str:
        return "\n".join(s.text for s in self.segments)
