"""Guard: config package stays settings-only."""

from __future__ import annotations

import re
from pathlib import Path

_FORBIDDEN = re.compile(
    r"^\s*(?:from|import)\s+archium\.(?:application|infrastructure|ui|workflow|agents)\b"
)


def test_config_does_not_import_outer_layers() -> None:
    root = Path(__file__).resolve().parents[2] / "archium" / "config"
    package_root = root.parent.parent
    hits: list[str] = []
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for match in _FORBIDDEN.finditer(text):
            line_no = text.count("\n", 0, match.start()) + 1
            hits.append(
                f"{path.relative_to(package_root)}:{line_no}: {match.group(0).strip()}"
            )
    assert hits == [], "config must stay settings-only:\n" + "\n".join(hits)
