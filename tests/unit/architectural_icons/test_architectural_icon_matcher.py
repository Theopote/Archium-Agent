"""Unit tests for Architectural Icon Registry semantic matching."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from archium.application.asset_matching_service import AssetMatchingService
from archium.application.visual.architectural_icon_registry import (
    ArchitecturalIconMatcher,
    load_default_architectural_icon_registry,
)
from archium.domain.enums import VisualType
from archium.domain.slide import SlideSpec, VisualRequirement


def test_registry_loads_bundled_icons() -> None:
    registry = load_default_architectural_icon_registry()
    icons = registry.all()
    assert len(icons) >= 30
    pedestrian = registry.get_by_name("pedestrian_flow")
    assert pedestrian is not None
    assert pedestrian.folder == "traffic"
    assert registry.resolve_svg_path(pedestrian).is_file()


def test_exact_semantic_name_match() -> None:
    match = ArchitecturalIconMatcher().match("pedestrian_flow")
    assert match is not None
    assert match.icon.canonical_name == "pedestrian_flow"
    assert match.matched_by == "exact_alias"
    assert match.score == 1.0


def test_alias_and_markup_match() -> None:
    matcher = ArchitecturalIconMatcher()
    zh = matcher.match("消防通道")
    assert zh is not None
    assert zh.icon.canonical_name == "emergency_access"

    marked = matcher.match("[[healing_garden]]")
    assert marked is not None
    assert marked.icon.canonical_name == "healing_garden"


def test_embedding_fallback_for_paraphrase() -> None:
    match = ArchitecturalIconMatcher().match("campus school learning")
    assert match is not None
    assert match.icon.canonical_name == "education"


def test_query_embedding_computed_once(monkeypatch) -> None:
    calls: list[str] = []

    def _track(text: str) -> list[float]:
        calls.append(text)
        from archium.infrastructure.embeddings.local_lexical import lexical_embed

        return lexical_embed(text)

    matcher = ArchitecturalIconMatcher(embed_query=_track)
    matcher.match("something_unrelated_xyz_for_embedding_scan")
    assert len(calls) == 1


def test_offline_embeddings_file_loaded() -> None:
    from archium.application.visual import architectural_icon_registry as reg

    pack = reg.default_icon_pack_root()
    assert (pack / "embeddings.json").is_file()
    registry = reg.load_architectural_icon_registry(pack)
    assert all(len(icon.embedding) >= 128 for icon in registry.all())
    source = Path(reg.__file__).read_text(encoding="utf-8")
    assert "from archium.infrastructure.embeddings.mock" not in source
    assert "MockEmbeddingProvider()" not in source


def test_asset_matching_binds_icon_id(db_session) -> None:
    slide = SlideSpec(
        presentation_id=uuid4(),
        chapter_id="ch1",
        order=0,
        title="流线",
        message="步行流线需要优先梳理。",
        visual_requirements=[
            VisualRequirement(
                type=VisualType.ICON,
                description="pedestrian_flow",
                required=True,
            )
        ],
    )
    service = AssetMatchingService(db_session)
    matched, count, changed = service._match_slide(
        slide,
        assets=[],
        qa_reports={},
        min_score=0.35,
        rematch=True,
        only_unmatched=False,
    )
    assert changed is True
    assert count == 1
    assert matched.visual_requirements[0].icon_id == "icon.pedestrian_flow"
    assert matched.visual_requirements[0].icon_canonical_name == "pedestrian_flow"
    assert matched.delivery_status.value == "ready"
