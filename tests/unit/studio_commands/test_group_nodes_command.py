"""Unit tests for GroupNodesCommand / UngroupNodesCommand / group move."""

from __future__ import annotations

from uuid import uuid4

import pytest
from archium.application.visual.studio_command_executor import (
    StudioCommandExecutor,
    StudioExecutionContext,
)
from archium.domain.visual.render_scene import (
    BackgroundStyle,
    GroupNode,
    RenderNode,
    RenderScene,
    ShapeNode,
    TextNode,
)
from archium.domain.visual.studio_command import (
    GroupNodesCommand,
    MoveNodeCommand,
    ResizeNodeCommand,
    UngroupNodesCommand,
)


def _text(node_id: str, *, x: float = 0.5, y: float = 0.5) -> TextNode:
    return TextNode(
        id=node_id,
        x=x,
        y=y,
        width=2.0,
        height=0.4,
        text=node_id,
        font_family="Arial",
        font_size=12,
        color="#000000",
        line_height=1.2,
    )


def _shape(node_id: str, *, x: float = 3.0, y: float = 2.0) -> ShapeNode:
    return ShapeNode(
        id=node_id,
        x=x,
        y=y,
        width=1.5,
        height=1.0,
        fill_color="#DDDDDD",
    )


def _scene(*nodes: RenderNode) -> RenderScene:
    return RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=10,
        page_height=5.625,
        background=BackgroundStyle(color="#FFFFFF"),
        nodes=list(nodes),
    )


def _ctx(scene: RenderScene) -> StudioExecutionContext:
    return StudioExecutionContext(presentation_id=uuid4(), validate_asset_bindings=False)


def test_group_nodes_creates_group_and_links_children() -> None:
    scene = _scene(_text("a"), _shape("b"))
    result = StudioCommandExecutor().execute(
        scene,
        GroupNodesCommand(
            presentation_id=uuid4(),
            slide_id=scene.slide_id,
            node_ids=["a", "b"],
            group_id="g_card",
        ),
        _ctx(scene),
    )
    assert result.success is True
    assert result.candidate_scene is not None
    group = result.candidate_scene.node_by_id("g_card")
    assert isinstance(group, GroupNode)
    assert group.children == ["a", "b"]
    assert result.candidate_scene.node_by_id("a").group_id == "g_card"
    assert result.candidate_scene.node_by_id("b").group_id == "g_card"
    assert group.source_layout_element_id == "g_card"


def test_group_nodes_rejects_single_member() -> None:
    scene = _scene(_text("a"), _shape("b"))
    result = StudioCommandExecutor().execute(
        scene,
        GroupNodesCommand(
            presentation_id=uuid4(),
            slide_id=scene.slide_id,
            node_ids=["a", "a"],
            group_id="g1",
        ),
        _ctx(scene),
    )
    assert result.success is False
    assert any(issue.code == "STUDIO.GROUP_TOO_FEW" for issue in result.issues)


def test_ungroup_clears_membership() -> None:
    scene = _scene(
        _text("a"),
        _shape("b"),
    )
    grouped = StudioCommandExecutor().execute(
        scene,
        GroupNodesCommand(
            presentation_id=uuid4(),
            slide_id=scene.slide_id,
            node_ids=["a", "b"],
            group_id="g1",
        ),
        _ctx(scene),
    ).candidate_scene
    assert grouped is not None
    result = StudioCommandExecutor().execute(
        grouped,
        UngroupNodesCommand(
            presentation_id=uuid4(),
            slide_id=grouped.slide_id,
            group_id="g1",
        ),
        _ctx(grouped),
    )
    assert result.success is True
    assert result.candidate_scene is not None
    assert result.candidate_scene.node_by_id("g1") is None
    assert result.candidate_scene.node_by_id("a").group_id is None
    assert result.candidate_scene.node_by_id("b").group_id is None


def test_move_group_moves_children() -> None:
    scene = _scene(_text("a", x=1.0, y=1.0), _shape("b", x=3.0, y=2.0))
    grouped = StudioCommandExecutor().execute(
        scene,
        GroupNodesCommand(
            presentation_id=uuid4(),
            slide_id=scene.slide_id,
            node_ids=["a", "b"],
            group_id="g1",
        ),
        _ctx(scene),
    ).candidate_scene
    assert grouped is not None
    group = grouped.node_by_id("g1")
    assert isinstance(group, GroupNode)
    dx, dy = 0.5, 0.25
    result = StudioCommandExecutor().execute(
        grouped,
        MoveNodeCommand(
            presentation_id=uuid4(),
            slide_id=grouped.slide_id,
            node_id="g1",
            x=group.x + dx,
            y=group.y + dy,
        ),
        _ctx(grouped),
    )
    assert result.success is True
    assert result.candidate_scene is not None
    assert result.candidate_scene.node_by_id("a").x == pytest.approx(1.0 + dx)
    assert result.candidate_scene.node_by_id("a").y == pytest.approx(1.0 + dy)
    assert result.candidate_scene.node_by_id("b").x == pytest.approx(3.0 + dx)
    assert result.candidate_scene.node_by_id("b").y == pytest.approx(2.0 + dy)


def test_resize_group_uniform_scales_children() -> None:
    scene = _scene(_text("a", x=1.0, y=1.0), _shape("b", x=3.0, y=2.0))
    grouped = StudioCommandExecutor().execute(
        scene,
        GroupNodesCommand(
            presentation_id=uuid4(),
            slide_id=scene.slide_id,
            node_ids=["a", "b"],
            group_id="g1",
        ),
        _ctx(scene),
    ).candidate_scene
    assert grouped is not None
    group = grouped.node_by_id("g1")
    assert isinstance(group, GroupNode)
    # Double the dominant size → uniform scale 2.
    result = StudioCommandExecutor().execute(
        grouped,
        ResizeNodeCommand(
            presentation_id=uuid4(),
            slide_id=grouped.slide_id,
            node_id="g1",
            x=group.x,
            y=group.y,
            width=group.width * 2,
            height=group.height * 2,
            preserve_aspect_ratio=True,
        ),
        _ctx(grouped),
    )
    assert result.success is True
    assert result.candidate_scene is not None
    child_a = result.candidate_scene.node_by_id("a")
    assert child_a.width == pytest.approx(4.0)
    assert child_a.height == pytest.approx(0.8)
