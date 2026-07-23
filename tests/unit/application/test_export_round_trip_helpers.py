"""Unit tests for export round-trip helper functions."""

from __future__ import annotations

from uuid import uuid4

from archium.application.export_round_trip_service import (
    _citation_integrity_checks,
    _derive_status,
    _drawing_integrity_checks,
    _geometry_match,
    _text_recall,
)
from archium.domain.export_round_trip import RoundTripStatus
from archium.domain.visual.render_scene import (
    BackgroundStyle,
    DrawingNode,
    ImageNode,
    RenderScene,
)
from archium.infrastructure.renderers.renderer_conformance import RendererSnapshot


def _scene(*nodes: object) -> RenderScene:
    return RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=10,
        page_height=5,
        background=BackgroundStyle(color="#FFFFFF"),
        nodes=list(nodes),  # type: ignore[arg-type]
    )


def test_text_recall_detects_missing_strings() -> None:
    rate, missing = _text_recall(("标题一", "标题二"), ("标题一", "其他"))
    assert rate == 0.5
    assert missing == ["标题二"]

    perfect, none_missing = _text_recall((), ("anything",))
    assert perfect == 1.0
    assert none_missing == []


def test_geometry_match_balances_node_and_image_counts() -> None:
    source = RendererSnapshot(
        node_count=4,
        text_values=("t1",),
        image_node_ids=("img1", "img2"),
        background_color="#ffffff",
    )
    exported = RendererSnapshot(
        node_count=4,
        text_values=("t1",),
        image_node_ids=("img1", "img2"),
        background_color="#ffffff",
    )
    assert _geometry_match(source, exported) == 1.0

    partial = RendererSnapshot(
        node_count=2,
        text_values=("t1",),
        image_node_ids=("img1",),
        background_color="#ffffff",
    )
    assert _geometry_match(source, partial) < 1.0


def test_drawing_integrity_checks_flags_fit_mode_and_metadata() -> None:
    scene = _scene(
        DrawingNode.model_construct(
            id="plan",
            node_type="drawing",
            x=0,
            y=0,
            width=8,
            height=4,
            z_index=1,
            storage_uri="asset://plan.png",
            fit_mode="cover",
            drawing_type="site_plan",
            north_arrow_visible=False,
            scale_label="",
            crop_allowed=True,
        ),
    )
    issues = _drawing_integrity_checks(scene)
    assert "plan:fit_mode=cover" in issues
    assert "plan:missing_north_or_scale" in issues
    assert "plan:crop_allowed_with_contain" not in issues


def test_citation_integrity_checks_reference_without_caption() -> None:
    scene = _scene(
        ImageNode(
            id="ref",
            x=0,
            y=0,
            width=4,
            height=3,
            z_index=1,
            storage_uri="asset://ref.png",
            asset_origin="reference_case",
        ),
    )
    assert _citation_integrity_checks(scene) == ["ref:reference_without_caption"]


def test_derive_status_prioritizes_blockers_and_review_thresholds() -> None:
    assert (
        _derive_status(
            text_match_rate=1.0,
            geometry_match_rate=1.0,
            similarity_score=1.0,
            drawing_issues=[],
            blockers=["blocked"],
            warnings=[],
        )
        == RoundTripStatus.BLOCKED
    )
    assert (
        _derive_status(
            text_match_rate=0.5,
            geometry_match_rate=1.0,
            similarity_score=1.0,
            drawing_issues=[],
            blockers=[],
            warnings=[],
        )
        == RoundTripStatus.NEEDS_REVIEW
    )
    assert (
        _derive_status(
            text_match_rate=1.0,
            geometry_match_rate=1.0,
            similarity_score=1.0,
            drawing_issues=["warn"],
            blockers=[],
            warnings=[],
        )
        == RoundTripStatus.PASS_WITH_WARNINGS
    )
    assert (
        _derive_status(
            text_match_rate=1.0,
            geometry_match_rate=1.0,
            similarity_score=1.0,
            drawing_issues=[],
            blockers=[],
            warnings=[],
        )
        == RoundTripStatus.PASS
    )
