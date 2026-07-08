"""skill 审核状态流转与技能库索引（drafts → skills，见产品定稿 spec §3）。"""

import logging
import re
import shutil
from pathlib import Path

from . import db

logger = logging.getLogger(__name__)

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def _read_frontmatter(md_path: Path) -> dict:
    m = _FRONTMATTER_RE.match(md_path.read_text(encoding="utf-8"))
    if not m:
        return {}
    fm: dict = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            fm[k.strip()] = v.strip()
    return fm


def _set_frontmatter_status(md_path: Path, status: str) -> None:
    text = md_path.read_text(encoding="utf-8")
    text = re.sub(r"^(status:).*$", rf"\1 {status}", text, count=1, flags=re.MULTILINE)
    md_path.write_text(text, encoding="utf-8")


def approve_skill(db_path: Path, kb_root: Path, skill_id: int, reviewer: str = "admin") -> bool:
    """采纳：drafts/{name} 整目录移入 skills/，frontmatter 置 approved，重建索引。"""
    with db.connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM skills WHERE id=? AND status='draft'", (skill_id,)
        ).fetchone()
        if row is None:
            return False
        src_dir = Path(row["md_path"]).parent
        dst_dir = kb_root / "skills" / row["name"]
        if src_dir.exists():
            dst_dir.parent.mkdir(parents=True, exist_ok=True)
            if dst_dir.exists():  # 同名旧版本：覆盖更新
                shutil.rmtree(dst_dir)
            shutil.move(str(src_dir), str(dst_dir))
            _set_frontmatter_status(dst_dir / "SKILL.md", "approved")
        conn.execute(
            "UPDATE skills SET status='approved', md_path=?, reviewed_by=?, "
            "reviewed_at=datetime('now') WHERE id=?",
            (str(dst_dir / "SKILL.md"), reviewer, skill_id),
        )
    rebuild_index(kb_root)
    return True


def reject_skill(db_path: Path, skill_id: int, reviewer: str = "admin") -> bool:
    """退回：状态置 rejected，文件留在 drafts 区备查（frontmatter 同步标记）。"""
    with db.connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM skills WHERE id=? AND status='draft'", (skill_id,)
        ).fetchone()
        if row is None:
            return False
        md_path = Path(row["md_path"])
        if md_path.exists():
            _set_frontmatter_status(md_path, "rejected")
        conn.execute(
            "UPDATE skills SET status='rejected', reviewed_by=?, "
            "reviewed_at=datetime('now') WHERE id=?",
            (reviewer, skill_id),
        )
    return True


def rebuild_index(kb_root: Path) -> Path:
    """扫描 skills/ 目录重建 INDEX.md（按 category 归组）。"""
    skills_dir = kb_root / "skills"
    by_category: dict[str, list[dict]] = {}
    if skills_dir.exists():
        for md in sorted(skills_dir.glob("*/SKILL.md")):
            fm = _read_frontmatter(md)
            fm["_rel"] = md.relative_to(kb_root).as_posix()
            by_category.setdefault(fm.get("category", "未分类"), []).append(fm)

    lines = [
        "# 技能库索引",
        "",
        "> 由 pipeline 自动维护（skills_store.rebuild_index），请勿手工编辑。",
        "> 仅收录已审核采纳（approved）的技能；草稿见 drafts/ 目录。",
        "",
    ]
    total = 0
    for category in sorted(by_category):
        lines.append(f"## {category}")
        lines.append("")
        for fm in by_category[category]:
            total += 1
            lines.append(
                f"- [{fm.get('name', '?')}]({fm['_rel']})"
                f"（confidence: {fm.get('confidence', '?')}）：{fm.get('description', '')}"
            )
        lines.append("")
    lines.insert(4, f"共 {total} 个技能。")

    kb_root.mkdir(parents=True, exist_ok=True)
    index = kb_root / "INDEX.md"
    index.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return index
