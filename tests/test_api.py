import pytest
from fastapi.testclient import TestClient

from pipeline.app import create_app
from pipeline.config import Settings
from pipeline.db import init_db
from pipeline.storage import save_transcript
from _samples import TRANSCRIPT, VIDEO


@pytest.fixture
def client(tmp_path):
    settings = Settings(
        db_path=tmp_path / "api.db", kb_root=tmp_path / "kb", work_dir=tmp_path / "work"
    )
    init_db(settings.db_path).close()
    app = create_app(settings, enable_worker=False)
    with TestClient(app) as c:
        c.settings = settings
        yield c


def test_healthz(client):
    assert client.get("/healthz").json() == {"ok": True}


def test_submit_and_list_and_detail(client):
    r = client.post("/api/tasks", json={"urls": ["BV1xx411c7XX", "https://b23.tv/abc"]})
    assert r.status_code == 200
    ids = r.json()["task_ids"]
    assert len(ids) == 2

    tasks = client.get("/api/tasks").json()["tasks"]
    assert len(tasks) == 2

    detail = client.get(f"/api/tasks/{ids[0]}").json()
    assert detail["status"] == "pending"
    assert detail["transcripts"] == []


def test_submit_empty_urls_rejected(client):
    assert client.post("/api/tasks", json={"urls": ["  "]}).status_code == 400


def test_retry_only_failed(client):
    tid = client.post("/api/tasks", json={"urls": ["BV1xx411c7XX"]}).json()["task_ids"][0]
    assert client.post(f"/api/tasks/{tid}/retry").status_code == 409


def test_admin_pages_render(client):
    assert "提交任务" in client.get("/admin").text
    assert "审核队列" in client.get("/admin/review").text


def test_admin_form_submit_and_detail_preview(client):
    r = client.post(
        "/admin/tasks", data={"urls": "BV1xx411c7XX\n\nBV1yy411c7YY"}, follow_redirects=False
    )
    assert r.status_code == 303

    # 构造一个已完成任务：落盘真实 transcript.md 并登记
    from pipeline import service
    vdir = save_transcript(client.settings.kb_root, VIDEO, TRANSCRIPT)
    tid = service.create_tasks(client.settings.db_path, ["BV1GJ411x7h7"])[0]
    service.add_transcript(
        client.settings.db_path, tid, "cc",
        str(vdir / "transcript.json"), str(vdir / "transcript.md"), 4000,
    )
    service.mark_done(client.settings.db_path, tid, {"video_count": 1})

    page = client.get(f"/admin/tasks/{tid}").text
    assert "大家好" in page          # 逐字稿预览
    assert "人工 CC 字幕" in page


def test_task_detail_404(client):
    assert client.get("/api/tasks/999").status_code == 404


def test_review_approve_and_reject_flow(client):
    from pipeline import service
    from pipeline.distiller import SkillDraft, render_skill_md

    def make(name):
        d = SkillDraft(name=name, title="标题", description="当…时使用", body="正文")
        ddir = client.settings.kb_root / "drafts" / name
        ddir.mkdir(parents=True)
        (ddir / "SKILL.md").write_text(render_skill_md(d, VIDEO), encoding="utf-8")
        [tid] = service.create_tasks(client.settings.db_path, [f"https://b23.tv/{name}"])
        return service.add_skill(client.settings.db_path, tid, name, "标题", str(ddir / "SKILL.md"))

    sid_a, sid_b = make("skill-a"), make("skill-b")

    page = client.get("/admin/review").text
    assert "skill-a" in page and "采纳" in page

    r = client.post(f"/admin/skills/{sid_a}/approve", follow_redirects=False)
    assert r.status_code == 303
    assert (client.settings.kb_root / "skills" / "skill-a" / "SKILL.md").exists()

    assert client.post(f"/admin/skills/{sid_b}/reject", follow_redirects=False).status_code == 303
    assert client.post(f"/admin/skills/{sid_b}/reject", follow_redirects=False).status_code == 409

    drafts = client.get("/api/skills/drafts").json()["drafts"]
    assert drafts == []
