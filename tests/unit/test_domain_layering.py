"""Guard: domain must not import application / infrastructure / ui / workflow / agents."""

from __future__ import annotations

import re
from pathlib import Path

_FORBIDDEN = re.compile(
    r"^\s*(?:from|import)\s+archium\.(?:application|infrastructure|ui|workflow|agents)\b"
)


def test_domain_does_not_import_outer_layers() -> None:
    root = Path(__file__).resolve().parents[2] / "archium" / "domain"
    hits: list[str] = []
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for match in _FORBIDDEN.finditer(text):
            line_no = text.count("\n", 0, match.start()) + 1
            hits.append(
                f"{path.relative_to(root.parent.parent)}:{line_no}: {match.group(0).strip()}"
            )
    assert hits == [], "domain layering violation:\n" + "\n".join(hits)


def test_scene_semantic_qa_duplicate_module_removed() -> None:
    root = Path(__file__).resolve().parents[2] / "archium" / "domain" / "visual"
    assert not (root / "scene_semantic_qa.py").exists()
    assert (root / "scene_qa.py").exists()
