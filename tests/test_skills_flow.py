"""drafts → 审核 → skills 状态流转与索引重建。"""

import pytest

from _samples import VIDEO
from pipeline import service, skills_store
from pipeline.db import init_db
from pipeline.distiller import SkillDraft, render_skill_md


@pytest.fixture
def env(tmp_path):
    db_path = tmp_path / "s.db"
    init_db(db_path).close()
    kb_root = tmp_path / "kb"
    return db_path, kb_root


def _make_draft(db_path, kb_root, name="api-rate-limit-design", category="工程实践") -> int:
    draft = SkillDraft(
        name=name, title="接口限频设计", category=category, confidence="high",
        description="当需要调用有风控的第三方接口时使用本技能", body="正文 [03:12]",
    )
    ddir = kb_root / "drafts" / name
    ddir.mkdir(parents=True)
    path = ddir / "SKILL.md"
    path.write_text(render_skill_md(draft, VIDEO), encoding="utf-8")
    [task_id] = service.create_tasks(db_path, [f"https://b23.tv/{name}"])
    return service.add_skill(db_path, task_id, name, draft.title, str(path))


def test_approve_moves_dir_updates_status_and_index(env):
    db_path, kb_root = env
    sid = _make_draft(db_path, kb_root)

    assert skills_store.approve_skill(db_path, kb_root, sid, reviewer="kwin")

    new_path = kb_root / "skills" / "api-rate-limit-design" / "SKILL.md"
    assert new_path.exists()
    assert not (kb_root / "drafts" / "api-rate-limit-design").exists()
    assert "status: approved" in new_path.read_text(encoding="utf-8")

    index = (kb_root / "INDEX.md").read_text(encoding="utf-8")
    assert "api-rate-limit-design" in index
    assert "工程实践" in index
    assert "共 1 个技能" in index

    assert service.list_skill_drafts(db_path) == []  # 队列清空
    assert not skills_store.approve_skill(db_path, kb_root, sid)  # 不可重复采纳


def test_reject_keeps_file_in_drafts(env):
    db_path, kb_root = env
    sid = _make_draft(db_path, kb_root)

    assert skills_store.reject_skill(db_path, sid)
    md = kb_root / "drafts" / "api-rate-limit-design" / "SKILL.md"
    assert md.exists()
    assert "status: rejected" in md.read_text(encoding="utf-8")
    assert service.list_skill_drafts(db_path) == []
    assert (kb_root / "skills").exists() is False


def test_add_skill_same_name_draft_is_updated_not_duplicated(env):
    db_path, kb_root = env
    sid1 = _make_draft(db_path, kb_root)
    [task2] = service.create_tasks(db_path, ["https://b23.tv/another"])
    sid2 = service.add_skill(db_path, task2, "api-rate-limit-design", "新标题", "/new/path.md")
    assert sid1 == sid2
    drafts = service.list_skill_drafts(db_path)
    assert len(drafts) == 1
    assert drafts[0]["title"] == "新标题"


def test_index_groups_by_category(env):
    db_path, kb_root = env
    for name, cat in [("skill-a", "工程实践"), ("skill-b", "避坑")]:
        sid = _make_draft(db_path, kb_root, name=name, category=cat)
        skills_store.approve_skill(db_path, kb_root, sid)
    index = (kb_root / "INDEX.md").read_text(encoding="utf-8")
    assert index.index("## 工程实践") < index.index("skill-a")
    assert "## 避坑" in index
    assert "共 2 个技能" in index
