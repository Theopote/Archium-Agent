"""Guard: domain must not import outer layers or heavy infra libs."""

from __future__ import annotations

import re
from pathlib import Path

_FORBIDDEN_ARCHIUM = re.compile(
    r"^\s*(?:from|import)\s+archium\.(?:application|infrastructure|ui|workflow|agents)\b"
)
_FORBIDDEN_LIBS = re.compile(
    r"^\s*(?:from|import)\s+(?:sqlalchemy|streamlit|chromadb)\b"
)


def _domain_root() -> Path:
    return Path(__file__).resolve().parents[2] / "archium" / "domain"


def _collect_hits(pattern: re.Pattern[str]) -> list[str]:
    root = _domain_root()
    package_root = root.parent.parent
    hits: list[str] = []
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for match in pattern.finditer(text):
            line_no = text.count("\n", 0, match.start()) + 1
            hits.append(
                f"{path.relative_to(package_root)}:{line_no}: {match.group(0).strip()}"
            )
    return hits


def test_domain_does_not_import_outer_layers() -> None:
    hits = _collect_hits(_FORBIDDEN_ARCHIUM)
    assert hits == [], "domain layering violation:\n" + "\n".join(hits)


def test_domain_does_not_import_infra_libraries() -> None:
    hits = _collect_hits(_FORBIDDEN_LIBS)
    assert hits == [], "domain must not import infra libraries:\n" + "\n".join(hits)


def test_visual_requirement_type_names_are_disambiguated() -> None:
    """DOM-016: slide vs schema requirements must not share a class name."""
    root = _domain_root()
    defining: list[str] = []
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "class VisualRequirement(" in text or "class VisualRequirement:" in text:
            defining.append(str(path.relative_to(root.parent.parent)))
    assert defining == [], f"bare VisualRequirement class still defined in: {defining}"

    from archium.domain.slide import SlideVisualRequirement, VisualRequirement
    from archium.domain.visual.architectural_content_schema import SchemaVisualRequirement

    assert SlideVisualRequirement is VisualRequirement
    assert SchemaVisualRequirement is not SlideVisualRequirement
    assert SchemaVisualRequirement.__name__ == "SchemaVisualRequirement"
    assert SlideVisualRequirement.__name__ == "SlideVisualRequirement"


def test_scene_semantic_qa_duplicate_module_removed() -> None:
    root = _domain_root() / "visual"
    assert not (root / "scene_semantic_qa.py").exists()
    assert not (root / "post_render_qa.py").exists()
    assert (root / "scene_qa.py").exists()
