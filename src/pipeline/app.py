"""核心服务：REST API + 管理后台（服务端渲染）+ 内置任务 worker。

启动：uvicorn pipeline.app:app --host 0.0.0.0 --port 8000
"""

import asyncio
import json
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from . import service
from .config import Settings, get_settings
from .db import init_db
from .worker import worker_loop

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

STATUS_DOC = {
    "pending": "排队中", "transcribing": "转写中", "distilling": "提炼中",
    "done": "完成", "failed": "失败",
}


class SubmitBody(BaseModel):
    urls: list[str]
    options: dict = {}


def create_app(settings: Settings | None = None, *, enable_worker: bool = True) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        init_db(settings.db_path)
        stop_event = asyncio.Event()
        task = asyncio.create_task(worker_loop(settings, stop_event=stop_event)) if enable_worker else None
        yield
        stop_event.set()
        if task:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    app = FastAPI(title="bili-knowledge-pipeline", lifespan=lifespan)

    # ---- REST API ---------------------------------------------------------

    @app.get("/healthz")
    def healthz() -> dict:
        return {"ok": True}

    @app.post("/api/tasks")
    def submit_tasks(body: SubmitBody) -> dict:
        urls = [u for u in (u.strip() for u in body.urls) if u]
        if not urls:
            raise HTTPException(400, "urls 不能为空")
        ids = service.create_tasks(settings.db_path, urls, source="admin", options=body.options)
        return {"task_ids": ids}

    @app.get("/api/tasks")
    def api_list_tasks(status: str = "", page: int = 1) -> dict:
        return {"tasks": service.list_tasks(settings.db_path, status=status, page=page)}

    @app.get("/api/tasks/{task_id}")
    def api_get_task(task_id: int) -> dict:
        task = service.get_task(settings.db_path, task_id)
        if task is None:
            raise HTTPException(404, "任务不存在")
        return task

    @app.post("/api/tasks/{task_id}/retry")
    def api_retry_task(task_id: int) -> dict:
        if not service.retry_task(settings.db_path, task_id):
            raise HTTPException(409, "仅 failed 状态的任务可重试")
        return {"ok": True}

    @app.get("/api/skills/drafts")
    def api_skill_drafts() -> dict:
        return {"drafts": service.list_skill_drafts(settings.db_path)}

    # ---- 管理后台（服务端渲染）--------------------------------------------

    @app.get("/")
    def index() -> RedirectResponse:
        return RedirectResponse("/admin")

    @app.get("/admin")
    def admin_home(request: Request, status: str = ""):
        tasks = service.list_tasks(settings.db_path, status=status, page_size=50)
        return templates.TemplateResponse(request, "index.html", {
            "tasks": tasks, "status": status, "status_doc": STATUS_DOC,
        })

    @app.post("/admin/tasks")
    def admin_submit(urls: str = Form(...), distill: bool = Form(False)):
        url_list = [u.strip() for u in urls.splitlines() if u.strip()]
        if url_list:
            service.create_tasks(
                settings.db_path, url_list, source="admin", options={"distill": distill}
            )
        return RedirectResponse("/admin", status_code=303)

    @app.post("/admin/tasks/{task_id}/retry")
    def admin_retry(task_id: int):
        service.retry_task(settings.db_path, task_id)
        return RedirectResponse("/admin", status_code=303)

    @app.get("/admin/tasks/{task_id}")
    def admin_task_detail(request: Request, task_id: int):
        task = service.get_task(settings.db_path, task_id)
        if task is None:
            raise HTTPException(404, "任务不存在")
        result = json.loads(task["result_json"]) if task.get("result_json") else None
        previews = []
        for t in task["transcripts"]:
            md_path = Path(t["md_path"])
            text = md_path.read_text(encoding="utf-8") if md_path.exists() else "(文件不存在)"
            previews.append({"source": t["source"], "path": t["md_path"], "text": text})
        return templates.TemplateResponse(request, "task_detail.html", {
            "task": task, "result": result, "previews": previews, "status_doc": STATUS_DOC,
        })

    @app.get("/admin/review")
    def admin_review(request: Request):
        drafts = service.list_skill_drafts(settings.db_path)
        return templates.TemplateResponse(request, "review.html", {"drafts": drafts})

    return app


app = create_app()
