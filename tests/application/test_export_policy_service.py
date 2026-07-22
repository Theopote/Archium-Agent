"""Tests for ExportPolicyService — fidelity assessment and policy enforcement."""

from __future__ import annotations

from uuid import uuid4

import pytest
from archium.application.export_policy_service import ExportPolicyService
from archium.domain.export_fidelity import ExportFidelityLevel, ExportPolicy
from archium.domain.visual.render_scene import (
    BackgroundStyle,
    DrawingNode,
    ImageNode,
    RenderScene,
    TextNode,
)
from archium.exceptions import WorkflowError


def _scene(*nodes: object) -> RenderScene:
    return RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=1920,
        page_height=1080,
        background=BackgroundStyle(color="#FFFFFF"),
        nodes=list(nodes),  # type: ignore[arg-type]
    )


def test_fully_editable_text_and_shapes() -> None:
    scene = _scene(
        TextNode(
            id="t1",
            x=100,
            y=100,
            width=400,
            height=80,
            z_index=1,
            text="标题",
            font_family="Arial",
            font_size=24,
            color="#000",
            line_height=1.2,
        ),
    )
    result = ExportPolicyService().assess_scene_fidelity(scene)
    assert result.fidelity_level == ExportFidelityLevel.FULLY_EDITABLE
    assert result.native_text_count == 1


def test_raster_fallback_single_full_page_image() -> None:
    scene = _scene(
        ImageNode(
            id="bg",
            x=0,
            y=0,
            width=1920,
            height=1080,
            z_index=0,
            storage_uri="asset://page.png",
        ),
    )
    result = ExportPolicyService().assess_scene_fidelity(scene)
    assert result.fidelity_level == ExportFidelityLevel.RASTER_FALLBACK


def test_drawing_cover_mode_is_blocker() -> None:
    scene = _scene(
        DrawingNode.model_construct(
            id="plan",
            node_type="drawing",
            x=100,
            y=100,
            width=800,
            height=600,
            z_index=1,
            storage_uri="asset://plan.png",
            fit_mode="cover",
        ),
    )
    result = ExportPolicyService().assess_scene_fidelity(scene)
    assert any("drawing:plan" in blocker for blocker in result.blockers)


def test_strict_policy_blocks_raster_export() -> None:
    service = ExportPolicyService()
    slide = service.assess_scene_fidelity(
        _scene(
            ImageNode(
                id="full",
                x=0,
                y=0,
                width=1920,
                height=1080,
                z_index=0,
                storage_uri="asset://full.png",
            ),
        )
    )
    manifest = service.build_deck_manifest(
        presentation_id=uuid4(),
        export_format="PPTX",
        policy=ExportPolicy(),
        slide_results=[slide],
    )
    with pytest.raises(WorkflowError, match="raster_fallback"):
        service.enforce_export_policy(manifest)


def test_allow_hybrid_per_slide_fallback_succeeds() -> None:
    service = ExportPolicyService()
    native = service.assess_scene_fidelity(
        _scene(
            TextNode(
                id="t1",
                x=10,
                y=10,
                width=200,
                height=40,
                z_index=1,
                text="说明",
                font_family="Arial",
                font_size=18,
                color="#000",
                line_height=1.2,
            ),
        )
    )
    hybrid = service.assess_scene_fidelity(
        _scene(
            TextNode(
                id="t2",
                x=10,
                y=10,
                width=200,
                height=40,
                z_index=2,
                text="混合页",
                font_family="Arial",
                font_size=18,
                color="#000",
                line_height=1.2,
            ),
            ImageNode(
                id="img",
                x=400,
                y=100,
                width=600,
                height=400,
                z_index=1,
                storage_uri="asset://photo.jpg",
            ),
        )
    )
    policy = ExportPolicy(allow_slide_level_fallback=True, allow_hybrid_editable=True)
    manifest = service.build_deck_manifest(
        presentation_id=uuid4(),
        export_format="PPTX",
        policy=policy,
        slide_results=[native, hybrid],
    )
    service.enforce_export_policy(manifest, policy=policy)
    assert manifest.fallback_used is True
    assert manifest.fidelity_counts[ExportFidelityLevel.HYBRID_EDITABLE] == 1
