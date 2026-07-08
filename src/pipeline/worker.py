"""任务队列 worker：轮询 SQLite 任务表，线程池里跑同步 pipeline。

- 启动时收编上次进程残留的中间态任务（重启恢复）
- 失败自动回 pending 重试（最多 MAX_ATTEMPTS 次，见 service.mark_failed）
- runner 可注入，测试时替换为假执行器
"""

import asyncio
import logging
from typing import Callable

from .config import Settings
from .runner import run_task
from .service import claim_next_pending, get_task, mark_done, mark_failed, recover_stuck_tasks

logger = logging.getLogger(__name__)

TaskRunner = Callable[[dict, Settings], dict]
# (task, result|None, outcome "done"|"failed") -> None；用于飞书完成通知等
TaskNotifier = Callable[[dict, dict | None, str], None]

POLL_INTERVAL = 2.0


async def worker_loop(
    settings: Settings,
    *,
    runner: TaskRunner = run_task,
    notifier: TaskNotifier | None = None,
    stop_event: asyncio.Event | None = None,
) -> None:
    recovered = recover_stuck_tasks(settings.db_path)
    if recovered:
        logger.info("启动恢复：%d 个中间态任务已回队列", recovered)

    stop_event = stop_event or asyncio.Event()
    loop = asyncio.get_running_loop()

    while not stop_event.is_set():
        task_row = claim_next_pending(settings.db_path)
        if task_row is None:
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=POLL_INTERVAL)
            except TimeoutError:
                pass
            continue

        task = dict(task_row)
        logger.info("任务 #%s 开始（第 %s 次尝试）: %s", task["id"], task["attempts"], task["url"])
        try:
            result = await loop.run_in_executor(None, runner, task, settings)
            mark_done(settings.db_path, task["id"], result)
            logger.info("任务 #%s 完成：%s 个视频", task["id"], result.get("video_count"))
            _notify(notifier, task, result, "done")
        except Exception as e:
            logger.exception("任务 #%s 失败", task["id"])
            mark_failed(settings.db_path, task["id"], f"{type(e).__name__}: {e}")
            final = get_task(settings.db_path, task["id"])
            if final and final["status"] == "failed":  # 重试次数耗尽才通知
                _notify(notifier, task, None, "failed")


def _notify(notifier: TaskNotifier | None, task: dict, result: dict | None, outcome: str) -> None:
    if notifier is None:
        return
    try:
        notifier(task, result, outcome)
    except Exception:
        logger.exception("任务 #%s 完成通知发送失败", task["id"])
