"""Guard: workflow package must not import UI."""

from __future__ import annotations

import re
from pathlib import Path

_FORBIDDEN = re.compile(r"^\s*(?:from|import)\s+archium\.ui\b")


def test_workflow_does_not_import_ui() -> None:
    root = Path(__file__).resolve().parents[2] / "archium" / "workflow"
    hits: list[str] = []
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for match in _FORBIDDEN.finditer(text):
            line_no = text.count("\n", 0, match.start()) + 1
            hits.append(
                f"{path.relative_to(root.parent.parent)}:{line_no}: {match.group(0).strip()}"
            )
    assert hits == [], "workflow must not import archium.ui:\n" + "\n".join(hits)
