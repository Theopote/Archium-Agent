"""ConnectorNode Studio command + PPTX adapter tests."""

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
    ConnectorEndpoint,
    ConnectorNode,
    RenderScene,
    ShapeNode,
)
from archium.domain.visual.studio_command import ConnectNodesCommand, MoveNodeCommand
from archium.infrastructure.renderers.scene_pptx_adapter import RenderScenePptxAdapter


def _shape(node_id: str, *, x: float, y: float) -> ShapeNode:
    return ShapeNode(
        id=node_id,
        x=x,
        y=y,
        width=1.0,
        height=1.0,
        fill_color="#CCCCCC",
    )


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


def test_connector_depth_is_partial() -> None:
    assert depth_entry("connector").status is PowerPointDepthStatus.PARTIAL


def test_connect_nodes_command_creates_connector() -> None:
    scene = _scene(_shape("a", x=1, y=1), _shape("b", x=4, y=3))
    result = StudioCommandExecutor().execute(
        scene,
        ConnectNodesCommand(
            presentation_id=uuid4(),
            slide_id=scene.slide_id,
            start_node_id="a",
            end_node_id="b",
            connector_id="cxn_test",
            start_anchor="right",
            end_anchor="left",
        ),
        _ctx(scene),
    )
    assert result.success is True
    assert result.candidate_scene is not None
    cxn = result.candidate_scene.node_by_id("cxn_test")
    assert isinstance(cxn, ConnectorNode)
    assert cxn.start.node_id == "a"
    assert cxn.end.node_id == "b"
    assert cxn.width > 0.05


def test_move_endpoint_refreshes_connector() -> None:
    a = _shape("a", x=1, y=1)
    b = _shape("b", x=4, y=1)
    cxn = ConnectorNode(
        id="c1",
        x=2.0,
        y=1.5,
        width=2.0,
        height=0.05,
        start=ConnectorEndpoint(node_id="a", anchor="right"),
        end=ConnectorEndpoint(node_id="b", anchor="left"),
    )
    scene = _scene(a, b, cxn)
    result = StudioCommandExecutor().execute(
        scene,
        MoveNodeCommand(
            presentation_id=uuid4(),
            slide_id=scene.slide_id,
            node_id="b",
            x=6.0,
            y=1.0,
        ),
        _ctx(scene),
    )
    assert result.success is True
    assert result.candidate_scene is not None
    live = result.candidate_scene.node_by_id("c1")
    assert isinstance(live, ConnectorNode)
    assert live.width == pytest.approx(4.0)
    assert any(action.action_type == "refresh_connector" for action in result.applied_actions)


def test_adapter_emits_connector_points_and_closure_passes() -> None:
    a = _shape("a", x=1, y=1)
    b = _shape("b", x=4, y=3)
    cxn = ConnectorNode(
        id="c1",
        x=2.0,
        y=1.5,
        width=2.0,
        height=2.0,
        start=ConnectorEndpoint(node_id="a", anchor="right"),
        end=ConnectorEndpoint(node_id="b", anchor="left"),
        arrow_end=True,
    )
    scene = _scene(a, b, cxn)
    instruction = RenderScenePptxAdapter().render_slide(scene)
    element = next(item for item in instruction.elements if item["id"] == "c1")
    assert element["content_type"] == "connector"
    assert len(element["points"]) >= 2
    assert element["arrow_end"] is True

    contracts = PowerPointContractService()
    emissions = contracts.plan_emissions(scene)
    report = contracts.validate_scene_closure(scene, emissions)
    assert report.valid, report.cardinality_violations
    assert any(item.source_scene_node_id == "c1" for item in emissions)
