"""runner 的提炼步骤：LLM 未配置时跳过；配置后草稿入库且任务状态经过 distilling。"""

import json

from _samples import TRANSCRIPT, VIDEO
from pipeline import service
from pipeline.config import Settings
from pipeline.db import init_db
from pipeline.runner import _distill_all


def _settings(tmp_path, **kw) -> Settings:
    s = Settings(db_path=tmp_path / "r.db", kb_root=tmp_path / "kb", work_dir=tmp_path / "w", **kw)
    init_db(s.db_path).close()
    return s


def test_distill_skipped_without_api_key(tmp_path):
    settings = _settings(tmp_path, llm_api_key="")
    result = _distill_all({"id": 1}, settings, [(VIDEO, TRANSCRIPT)], llm=None)
    assert "skipped" in result


def test_distill_registers_drafts(tmp_path):
    settings = _settings(tmp_path)
    [tid] = service.create_tasks(settings.db_path, ["BV1GJ411x7h7"])

    class FakeLLM:
        def chat(self, system, user):
            if "编辑" in system:
                return "整理稿"
            return json.dumps([{
                "name": "test-skill", "title": "T",
                "description": "当…时使用", "body": "正文",
            }], ensure_ascii=False)

    result = _distill_all({"id": tid}, settings, [(VIDEO, TRANSCRIPT)], llm=FakeLLM())
    assert result["draft_count"] == 1
    assert result["names"] == ["test-skill"]

    drafts = service.list_skill_drafts(settings.db_path)
    assert len(drafts) == 1
    assert drafts[0]["task_id"] == tid
    # 提炼中状态被写过（最终状态由 worker 的 mark_done 决定，这里应为 distilling）
    assert service.get_task(settings.db_path, tid)["status"] == "distilling"
