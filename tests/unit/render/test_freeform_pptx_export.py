"""FreeformNode Studio command + PPTX adapter tests."""

from __future__ import annotations

from uuid import uuid4

import pytest
from archium.application.visual.studio_command_executor import (
    StudioCommandExecutor,
    StudioExecutionContext,
)
from archium.domain.powerpoint_capability import PowerPointDepthStatus, depth_entry
from archium.domain.powerpoint_contract import PowerPointContractService
from archium.domain.visual.render_scene import (
    BackgroundStyle,
    FreeformNode,
    RenderScene,
    freeform_preset_points,
)
from archium.domain.visual.studio_command import CreateFreeformCommand, MoveNodeCommand
from archium.infrastructure.renderers.scene_pptx_adapter import RenderScenePptxAdapter


def _scene(*nodes: object) -> RenderScene:
    return RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=10,
        page_height=5.625,
        background=BackgroundStyle(color="#FFFFFF"),
        nodes=list(nodes),  # type: ignore[arg-type]
    )


def _ctx(scene: RenderScene) -> StudioExecutionContext:
    return StudioExecutionContext(presentation_id=uuid4(), validate_asset_bindings=False)


def test_freeform_depth_is_partial() -> None:
    assert depth_entry("freeform_path").status is PowerPointDepthStatus.PARTIAL


def test_create_freeform_triangle_command() -> None:
    scene = _scene()
    result = StudioCommandExecutor().execute(
        scene,
        CreateFreeformCommand(
            presentation_id=uuid4(),
            slide_id=scene.slide_id,
            preset="triangle",
            x=2.0,
            y=1.0,
            width=3.0,
            height=2.0,
            freeform_id="ff_test",
        ),
        _ctx(scene),
    )
    assert result.success is True
    assert result.candidate_scene is not None
    node = result.candidate_scene.node_by_id("ff_test")
    assert isinstance(node, FreeformNode)
    assert len(node.points) == 3
    assert node.width == pytest.approx(3.0)


def test_move_freeform_translates_points() -> None:
    points = freeform_preset_points("triangle", x=1, y=1, width=2, height=2)
    node = FreeformNode(
        id="ff1",
        x=1,
        y=1,
        width=2,
        height=2,
        points=points,
    )
    scene = _scene(node)
    result = StudioCommandExecutor().execute(
        scene,
        MoveNodeCommand(
            presentation_id=uuid4(),
            slide_id=scene.slide_id,
            node_id="ff1",
            x=3.0,
            y=2.0,
        ),
        _ctx(scene),
    )
    assert result.success is True
    assert result.candidate_scene is not None
    moved = result.candidate_scene.node_by_id("ff1")
    assert isinstance(moved, FreeformNode)
    assert moved.x == pytest.approx(3.0)
    assert moved.y == pytest.approx(2.0)
    assert min(p.x for p in moved.points) == pytest.approx(3.0)


def test_adapter_emits_freeform_points_and_closure_passes() -> None:
    points = freeform_preset_points("diamond", x=1, y=1, width=2, height=2)
    node = FreeformNode(
        id="ff1",
        x=1,
        y=1,
        width=2,
        height=2,
        points=points,
        fill_color="#E8F0FE",
        stroke_color="#1A73E8",
    )
    scene = _scene(node)
    instruction = RenderScenePptxAdapter().render_slide(scene)
    element = next(item for item in instruction.elements if item["id"] == "ff1")
    assert element["content_type"] == "freeform"
    assert len(element["points"]) == 4
    assert element["closed"] is True

    contracts = PowerPointContractService()
    emissions = contracts.plan_emissions(scene)
    report = contracts.validate_scene_closure(scene, emissions)
    assert report.valid, report.cardinality_violations
    assert any(item.source_scene_node_id == "ff1" for item in emissions)
