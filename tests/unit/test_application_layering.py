"""Guard: application must not import UI modules or agents private helpers."""

from __future__ import annotations

import re
from pathlib import Path

_FORBIDDEN = re.compile(r"^\s*(?:from|import)\s+archium\.ui\b")
_AGENTS_HELPERS = re.compile(
    r"^\s*(?:from|import)\s+archium\.agents\._helpers\b"
)


def test_application_does_not_import_ui() -> None:
    root = Path(__file__).resolve().parents[2] / "archium" / "application"
    hits: list[str] = []
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for match in _FORBIDDEN.finditer(text):
            line_no = text.count("\n", 0, match.start()) + 1
            hits.append(
                f"{path.relative_to(root.parent.parent)}:{line_no}: {match.group(0).strip()}"
            )
    assert hits == [], "application must not import archium.ui:\n" + "\n".join(hits)


def test_application_does_not_import_agents_private_helpers() -> None:
    root = Path(__file__).resolve().parents[2] / "archium" / "application"
    hits: list[str] = []
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for match in _AGENTS_HELPERS.finditer(text):
            line_no = text.count("\n", 0, match.start()) + 1
            hits.append(
                f"{path.relative_to(root.parent.parent)}:{line_no}: {match.group(0).strip()}"
            )
    assert hits == [], (
        "application must import archium.application._helpers, "
        "not archium.agents._helpers:\n" + "\n".join(hits)
    )


_ORM_IMPORT = re.compile(
    r"^\s*(?:from|import)\s+archium\.infrastructure\.database\.models\b"
)


def test_application_does_not_import_orm_models() -> None:
    root = Path(__file__).resolve().parents[2] / "archium" / "application"
    hits: list[str] = []
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for match in _ORM_IMPORT.finditer(text):
            line_no = text.count("\n", 0, match.start()) + 1
            hits.append(
                f"{path.relative_to(root.parent.parent)}:{line_no}: {match.group(0).strip()}"
            )
    assert hits == [], "application must use repositories, not ORM models:\n" + "\n".join(hits)
