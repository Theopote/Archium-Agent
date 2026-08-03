"""Guard: UI must not import ORM models (use repositories / application services)."""

from __future__ import annotations

import re
from pathlib import Path

_ORM_IMPORT = re.compile(
    r"^\s*(?:from|import)\s+archium\.infrastructure\.database\.models\b"
)
_REPO_IMPORT = re.compile(
    r"^\s*(?:from|import)\s+archium\.infrastructure\.database\.repositories\b"
)


def test_ui_does_not_import_orm_models() -> None:
    root = Path(__file__).resolve().parents[2] / "archium" / "ui"
    package_root = root.parent.parent
    hits: list[str] = []
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for match in _ORM_IMPORT.finditer(text):
            line_no = text.count("\n", 0, match.start()) + 1
            hits.append(
                f"{path.relative_to(package_root)}:{line_no}: {match.group(0).strip()}"
            )
    assert hits == [], "ui must not import ORM models:\n" + "\n".join(hits)


def test_ui_pages_do_not_import_repositories() -> None:
    """APP-029: Streamlit pages go through Application API, not repositories."""
    root = Path(__file__).resolve().parents[2] / "archium" / "ui" / "pages"
    package_root = root.parent.parent.parent
    hits: list[str] = []
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for match in _REPO_IMPORT.finditer(text):
            line_no = text.count("\n", 0, match.start()) + 1
            hits.append(
                f"{path.relative_to(package_root)}:{line_no}: {match.group(0).strip()}"
            )
    assert hits == [], "ui pages must not import repositories:\n" + "\n".join(hits)
