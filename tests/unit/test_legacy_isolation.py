"""Guard: archium must not import the in-tree legacy package."""

from __future__ import annotations

import re
from pathlib import Path

_IMPORT_RE = re.compile(r"^\s*(?:from\s+legacy(?:\.|\s)|import\s+legacy(?:\.|\s|$))", re.M)


def test_archium_package_does_not_import_legacy() -> None:
    root = Path(__file__).resolve().parents[2] / "archium"
    hits: list[str] = []
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for match in _IMPORT_RE.finditer(text):
            line_no = text.count("\n", 0, match.start()) + 1
            hits.append(f"{path.relative_to(root.parent)}:{line_no}: {match.group(0).strip()}")
    assert hits == [], "archium must not import legacy:\n" + "\n".join(hits)
