import asyncio

import pytest

from pipeline import service
from pipeline.config import Settings
from pipeline.db import connect, init_db
from pipeline.worker import worker_loop


@pytest.fixture
def settings(tmp_path) -> Settings:
    s = Settings(db_path=tmp_path / "w.db", kb_root=tmp_path / "kb", work_dir=tmp_path / "work")
    init_db(s.db_path).close()
    return s


async def _run_until(settings, runner, predicate, timeout=5.0):
    stop = asyncio.Event()
    task = asyncio.create_task(worker_loop(settings, runner=runner, stop_event=stop))
    try:
        async with asyncio.timeout(timeout):
            while not predicate():
                await asyncio.sleep(0.05)
    finally:
        stop.set()
        await task


@pytest.mark.anyio
async def test_worker_processes_task_to_done(settings):
    [tid] = service.create_tasks(settings.db_path, ["BV1xx411c7XX"])

    def fake_runner(task, _settings):
        return {"video_count": 1, "bvid": "BV1xx411c7XX", "title": "t", "videos": []}

    await _run_until(
        settings, fake_runner,
        lambda: service.get_task(settings.db_path, tid)["status"] == "done",
    )
    assert service.get_task(settings.db_path, tid)["status"] == "done"


@pytest.mark.anyio
async def test_worker_retries_then_fails(settings):
    [tid] = service.create_tasks(settings.db_path, ["BV1xx411c7XX"])

    def broken_runner(task, _settings):
        raise RuntimeError("boom")

    await _run_until(
        settings, broken_runner,
        lambda: service.get_task(settings.db_path, tid)["status"] == "failed",
    )
    task = service.get_task(settings.db_path, tid)
    assert task["attempts"] == service.MAX_ATTEMPTS
    assert "boom" in task["error"]


@pytest.mark.anyio
async def test_worker_recovers_stuck_task_on_start(settings):
    [tid] = service.create_tasks(settings.db_path, ["BV1xx411c7XX"])
    with connect(settings.db_path) as conn:
        conn.execute("UPDATE tasks SET status='transcribing' WHERE id=?", (tid,))

    def fake_runner(task, _settings):
        return {"video_count": 1, "videos": [], "bvid": "x", "title": "t"}

    await _run_until(
        settings, fake_runner,
        lambda: service.get_task(settings.db_path, tid)["status"] == "done",
    )


@pytest.mark.anyio
async def test_worker_notifier_called_on_done_and_final_failure(settings):
    ids = service.create_tasks(settings.db_path, ["BV1aa411c7XX", "BV1bb411c7XX"])
    notifications: list[tuple[int, str]] = []

    def runner(task, _settings):
        if task["url"] == "BV1aa411c7XX":
            return {"video_count": 1, "videos": [], "bvid": "a", "title": "t"}
        raise RuntimeError("always fails")

    def notifier(task, result, outcome):
        notifications.append((task["id"], outcome))

    async def all_settled():
        stop = asyncio.Event()
        t = asyncio.create_task(
            worker_loop(settings, runner=runner, notifier=notifier, stop_event=stop)
        )
        async with asyncio.timeout(10):
            while True:
                statuses = {x["status"] for x in service.list_tasks(settings.db_path)}
                if statuses == {"done", "failed"}:
                    break
                await asyncio.sleep(0.05)
        stop.set()
        await t

    await all_settled()
    # done 通知 1 次；failed 仅在重试耗尽的最后一次通知 1 次
    assert notifications.count((ids[0], "done")) == 1
    assert notifications.count((ids[1], "failed")) == 1


@pytest.fixture
def anyio_backend():
    return "asyncio"
