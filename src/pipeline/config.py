from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # B 站
    bili_sessdata: str = ""          # 抓 AI 字幕必需，未配置时字幕直抓大概率拿不到 subtitle_url
    bili_min_interval: float = 3.0   # B 站接口最小请求间隔（秒），另加随机抖动

    # ASR 兜底
    whisper_model: str = "small"     # faster-whisper 模型：small / medium / large-v3
    whisper_device: str = "auto"
    downloader: str = "bbdown"       # bbdown | yt-dlp

    # LLM（M3 使用）
    llm_base_url: str = "https://api.deepseek.com"
    llm_api_key: str = ""
    llm_model: str = "deepseek-chat"

    # 飞书（M4 使用）
    feishu_app_id: str = ""
    feishu_app_secret: str = ""
    feishu_alert_chat_id: str = ""   # 任务失败告警群（后台来源任务也会通知到这里）

    # 管理后台
    admin_token: str = ""            # 设置后 /admin 与 /api 需携带口令（X-Admin-Token 头或 ?token=）

    # 存储
    kb_root: Path = Path("./knowledge-base")
    db_path: Path = Path("./data/pipeline.db")
    work_dir: Path = Path("./data/work")  # 音视频临时下载目录
    project_context_file: Path = Path("./project-context.md")


@lru_cache
def get_settings() -> Settings:
    return Settings()
