from pathlib import Path

import pytest

from pipeline import service
from pipeline.db import connect, init_db


@pytest.fixture
def db_path(tmp_path) -> Path:
    p = tmp_path / "test.db"
    init_db(p).close()
    return p


def test_create_tasks_batch_and_idempotent(db_path):
    ids = service.create_tasks(db_path, ["https://b23.tv/a", "BV1xx411c7XX", "  "])
    assert len(ids) == 2
    # 同 URL 未完成时不重复建
    ids2 = service.create_tasks(db_path, ["https://b23.tv/a"])
    assert ids2 == [ids[0]]


def test_claim_marks_transcribing_and_increments_attempts(db_path):
    [tid] = service.create_tasks(db_path, ["BV1xx411c7XX"])
    row = service.claim_next_pending(db_path)
    assert row["id"] == tid
    assert row["status"] == "transcribing"
    assert row["attempts"] == 1
    assert service.claim_next_pending(db_path) is None  # 队列空


def test_mark_failed_requeues_until_max_attempts(db_path):
    [tid] = service.create_tasks(db_path, ["BV1xx411c7XX"])
    for attempt in range(1, service.MAX_ATTEMPTS + 1):
        row = service.claim_next_pending(db_path)
        assert row is not None, f"第 {attempt} 次应能领到任务"
        service.mark_failed(db_path, tid, "boom")
    task = service.get_task(db_path, tid)
    assert task["status"] == "failed"
    assert task["attempts"] == service.MAX_ATTEMPTS


def test_retry_resets_failed_task(db_path):
    [tid] = service.create_tasks(db_path, ["BV1xx411c7XX"])
    with connect(db_path) as conn:
        conn.execute("UPDATE tasks SET status='failed', attempts=3 WHERE id=?", (tid,))
    assert service.retry_task(db_path, tid)
    task = service.get_task(db_path, tid)
    assert task["status"] == "pending"
    assert task["attempts"] == 0
    assert not service.retry_task(db_path, tid)  # 非 failed 不可重试


def test_recover_stuck_tasks(db_path):
    ids = service.create_tasks(db_path, ["BV1aa411c7XX", "BV1bb411c7XX"])
    with connect(db_path) as conn:
        conn.execute("UPDATE tasks SET status='transcribing' WHERE id=?", (ids[0],))
        conn.execute("UPDATE tasks SET status='distilling' WHERE id=?", (ids[1],))
    assert service.recover_stuck_tasks(db_path) == 2
    assert all(t["status"] == "pending" for t in service.list_tasks(db_path))


def test_mark_done_stores_result_and_transcripts(db_path):
    [tid] = service.create_tasks(db_path, ["BV1xx411c7XX"])
    service.add_transcript(db_path, tid, "cc", "/kb/a.json", "/kb/a.md", 600)
    service.mark_done(db_path, tid, {"video_count": 1})
    task = service.get_task(db_path, tid)
    assert task["status"] == "done"
    assert task["transcripts"][0]["md_path"] == "/kb/a.md"


def test_list_tasks_filters_by_status(db_path):
    service.create_tasks(db_path, ["BV1aa411c7XX", "BV1bb411c7XX"])
    service.claim_next_pending(db_path)
    assert len(service.list_tasks(db_path, status="pending")) == 1
    assert len(service.list_tasks(db_path)) == 2
