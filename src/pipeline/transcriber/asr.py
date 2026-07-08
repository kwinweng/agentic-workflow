"""transcriber 路线 B 的 ASR 引擎抽象。

引擎可插拔（见架构文档 §3.2）：默认 faster-whisper，预留 FunASR。
faster-whisper 为可选依赖（pip install .[asr]），惰性导入。
"""

from pathlib import Path
from typing import Protocol

from ..models import Segment


class AsrEngine(Protocol):
    def transcribe(self, audio_path: Path) -> tuple[str, list[Segment]]:
        """返回 (language, segments)。"""
        ...


class FasterWhisperEngine:
    def __init__(self, model_size: str = "small", device: str = "auto"):
        self._model_size = model_size
        self._device = device
        self._model = None

    def _load(self):
        if self._model is None:
            try:
                from faster_whisper import WhisperModel
            except ImportError as e:
                raise RuntimeError(
                    "faster-whisper 未安装，ASR 兜底不可用。安装：pip install '.[asr]'"
                ) from e
            self._model = WhisperModel(
                self._model_size, device=self._device, compute_type="int8"
            )
        return self._model

    def transcribe(self, audio_path: Path) -> tuple[str, list[Segment]]:
        model = self._load()
        raw_segments, info = model.transcribe(
            str(audio_path), language="zh", vad_filter=True
        )
        segments = [
            Segment(start=s.start, end=s.end, text=s.text.strip())
            for s in raw_segments
            if s.text.strip()
        ]
        return info.language or "zh", segments


def create_engine(name: str = "faster-whisper", **kwargs) -> AsrEngine:
    if name == "faster-whisper":
        return FasterWhisperEngine(**kwargs)
    raise ValueError(f"未知 ASR 引擎: {name}")
