import sqlite3
from pathlib import Path

# 数据模型见 docs/02-架构设计.md §4；cards 表按 2026-07-08 产品定稿改为 skills 表
SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL,
    bvid TEXT,
    cid INTEGER,
    title TEXT,
    source TEXT NOT NULL DEFAULT 'admin',      -- feishu | admin | cli
    options_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'pending',
    -- pending|transcribing|distilling|done|failed
    error TEXT,
    attempts INTEGER NOT NULL DEFAULT 0,
    result_json TEXT,                          -- 完成后的产物摘要（视频数/落盘路径等）
    feishu_chat_id TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS transcripts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER REFERENCES tasks(id),
    source TEXT NOT NULL,                      -- cc | ai-subtitle | whisper
    json_path TEXT NOT NULL,
    md_path TEXT NOT NULL,
    duration_sec INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS feishu_events (
    event_id TEXT PRIMARY KEY,                 -- 飞书事件去重
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS skills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER REFERENCES tasks(id),
    name TEXT NOT NULL,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',      -- draft | approved | rejected
    md_path TEXT NOT NULL,
    reviewed_by TEXT,
    reviewed_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def connect(db_path: Path) -> sqlite3.Connection:
    """每次操作开新连接（sqlite 单机足够），WAL 模式支持 worker 与 API 并发读写。"""
    conn = sqlite3.connect(db_path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(db_path)
    conn.executescript(SCHEMA)
    return conn
