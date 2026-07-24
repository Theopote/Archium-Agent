"""Guard: infrastructure must not import application (layering phase-1/2)."""

from __future__ import annotations

import re
from pathlib import Path

_APPLICATION_IMPORT = re.compile(r"^\s*(?:from|import)\s+archium\.application\b")
_UI_IMPORT = re.compile(r"^\s*(?:from|import)\s+archium\.ui\b")


def test_infrastructure_does_not_import_application() -> None:
    root = Path(__file__).resolve().parents[2] / "archium" / "infrastructure"
    package_root = root.parent.parent
    hits: list[str] = []
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for match in _APPLICATION_IMPORT.finditer(text):
            line_no = text.count("\n", 0, match.start()) + 1
            hits.append(
                f"{path.relative_to(package_root)}:{line_no}: {match.group(0).strip()}"
            )
    assert hits == [], (
        "infrastructure must not import archium.application "
        "(inject ports from application/workflow composition roots):\n"
        + "\n".join(hits)
    )


def test_infrastructure_does_not_import_ui() -> None:
    root = Path(__file__).resolve().parents[2] / "archium" / "infrastructure"
    package_root = root.parent.parent
    hits: list[str] = []
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for match in _UI_IMPORT.finditer(text):
            line_no = text.count("\n", 0, match.start()) + 1
            hits.append(
                f"{path.relative_to(package_root)}:{line_no}: {match.group(0).strip()}"
            )
    assert hits == [], "infrastructure must not import archium.ui:\n" + "\n".join(hits)
