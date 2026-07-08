"""任务表即队列：任务生命周期操作（被 REST API、worker、飞书入口共用）。"""

import json
import sqlite3
from pathlib import Path

from . import db

MAX_ATTEMPTS = 3

# worker 崩溃/重启时可能残留的中间状态，启动时收编回 pending
_STUCK_STATUSES = ("transcribing", "distilling")


def create_tasks(
    db_path: Path, urls: list[str], *, source: str = "admin",
    options: dict | None = None, feishu_chat_id: str = "",
) -> list[int]:
    """批量建任务（一条 URL 一个任务），返回任务 id 列表。

    幂等：同 URL 已存在未完成（pending/进行中）任务时不重复创建，返回已有任务 id。
    """
    options_json = json.dumps(options or {}, ensure_ascii=False)
    ids: list[int] = []
    with db.connect(db_path) as conn:
        for url in urls:
            url = url.strip()
            if not url:
                continue
            row = conn.execute(
                "SELECT id FROM tasks WHERE url=? AND status IN ('pending','transcribing','distilling')",
                (url,),
            ).fetchone()
            if row:
                ids.append(row["id"])
                continue
            cur = conn.execute(
                "INSERT INTO tasks (url, source, options_json, feishu_chat_id) VALUES (?,?,?,?)",
                (url, source, options_json, feishu_chat_id),
            )
            ids.append(cur.lastrowid)
    return ids


def claim_next_pending(db_path: Path) -> sqlite3.Row | None:
    """原子认领下一个 pending 任务并置为 transcribing。"""
    with db.connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM tasks WHERE status='pending' ORDER BY id LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        updated = conn.execute(
            "UPDATE tasks SET status='transcribing', attempts=attempts+1, "
            "updated_at=datetime('now') WHERE id=? AND status='pending'",
            (row["id"],),
        ).rowcount
        if not updated:  # 被并发 worker 抢走
            return None
        return conn.execute("SELECT * FROM tasks WHERE id=?", (row["id"],)).fetchone()


def mark_done(db_path: Path, task_id: int, result: dict) -> None:
    with db.connect(db_path) as conn:
        conn.execute(
            "UPDATE tasks SET status='done', error=NULL, result_json=?, "
            "updated_at=datetime('now') WHERE id=?",
            (json.dumps(result, ensure_ascii=False), task_id),
        )


def mark_failed(db_path: Path, task_id: int, error: str) -> None:
    """失败：未达最大重试次数回 pending 重试，否则置 failed。"""
    with db.connect(db_path) as conn:
        row = conn.execute("SELECT attempts FROM tasks WHERE id=?", (task_id,)).fetchone()
        status = "failed" if row and row["attempts"] >= MAX_ATTEMPTS else "pending"
        conn.execute(
            "UPDATE tasks SET status=?, error=?, updated_at=datetime('now') WHERE id=?",
            (status, error[:1000], task_id),
        )


def recover_stuck_tasks(db_path: Path) -> int:
    """启动恢复：把上次进程退出时残留的中间态任务收编回 pending。"""
    placeholders = ",".join("?" for _ in _STUCK_STATUSES)
    with db.connect(db_path) as conn:
        return conn.execute(
            f"UPDATE tasks SET status='pending', updated_at=datetime('now') "
            f"WHERE status IN ({placeholders})",
            _STUCK_STATUSES,
        ).rowcount


def retry_task(db_path: Path, task_id: int) -> bool:
    """人工重试：failed 任务重置为 pending 并清零重试计数。"""
    with db.connect(db_path) as conn:
        return bool(
            conn.execute(
                "UPDATE tasks SET status='pending', attempts=0, error=NULL, "
                "updated_at=datetime('now') WHERE id=? AND status='failed'",
                (task_id,),
            ).rowcount
        )


def get_task(db_path: Path, task_id: int) -> dict | None:
    with db.connect(db_path) as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        if row is None:
            return None
        task = dict(row)
        task["transcripts"] = [
            dict(t) for t in conn.execute(
                "SELECT * FROM transcripts WHERE task_id=?", (task_id,)
            ).fetchall()
        ]
        return task


def list_tasks(db_path: Path, status: str = "", page: int = 1, page_size: int = 20) -> list[dict]:
    where = "WHERE status=?" if status else ""
    params: tuple = (status,) if status else ()
    with db.connect(db_path) as conn:
        rows = conn.execute(
            f"SELECT * FROM tasks {where} ORDER BY id DESC LIMIT ? OFFSET ?",
            (*params, page_size, (page - 1) * page_size),
        ).fetchall()
        return [dict(r) for r in rows]


def add_transcript(
    db_path: Path, task_id: int, source: str, json_path: str, md_path: str, duration_sec: int
) -> None:
    with db.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO transcripts (task_id, source, json_path, md_path, duration_sec) "
            "VALUES (?,?,?,?,?)",
            (task_id, source, json_path, md_path, duration_sec),
        )


def list_skill_drafts(db_path: Path) -> list[dict]:
    """审核队列：M3 产出 skill 草稿后由此消费。"""
    with db.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM skills WHERE status='draft' ORDER BY id DESC"
        ).fetchall()
        return [dict(r) for r in rows]
