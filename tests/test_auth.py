import pytest
from fastapi.testclient import TestClient

from pipeline.app import create_app
from pipeline.config import Settings
from pipeline.db import init_db


@pytest.fixture
def client(tmp_path):
    settings = Settings(
        db_path=tmp_path / "a.db", kb_root=tmp_path / "kb",
        work_dir=tmp_path / "w", admin_token="secret-token",
    )
    init_db(settings.db_path).close()
    with TestClient(create_app(settings, enable_worker=False)) as c:
        yield c


def test_healthz_exempt(client):
    assert client.get("/healthz").status_code == 200


def test_admin_requires_token(client):
    assert client.get("/admin").status_code == 401
    assert client.get("/api/tasks").status_code == 401


def test_header_token_accepted(client):
    r = client.get("/api/tasks", headers={"X-Admin-Token": "secret-token"})
    assert r.status_code == 200


def test_query_token_sets_cookie_for_subsequent_requests(client):
    assert client.get("/admin?token=wrong").status_code == 401
    assert client.get("/admin?token=secret-token").status_code == 200
    # cookie 已种，后续不带 token 也可访问
    assert client.get("/admin").status_code == 200
