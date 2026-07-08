FROM python:3.11-slim

# ffmpeg：抽帧与音频处理；yt-dlp 走 pip 安装（镜像内默认下载工具）
# BBDown 是 .NET 单文件，如需改用请挂载二进制并设 DOWNLOADER=bbdown
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir ".[asr,feishu]" yt-dlp

# faster-whisper 模型在首次转写时自动下载到 /root/.cache（可用卷持久化）
ENV DOWNLOADER=yt-dlp \
    KB_ROOT=/data/knowledge-base \
    DB_PATH=/data/pipeline.db \
    WORK_DIR=/data/work

VOLUME ["/data"]
EXPOSE 8000

# 默认启动管理后台+worker；飞书机器人模式改 command 为 python -m pipeline.feishu_bot
CMD ["uvicorn", "pipeline.app:app", "--host", "0.0.0.0", "--port", "8000"]
