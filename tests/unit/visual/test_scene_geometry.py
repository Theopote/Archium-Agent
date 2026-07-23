"""Unit tests for scene geometry helpers."""

from __future__ import annotations

from uuid import uuid4

import pytest
from archium.application.visual.scene_geometry import (
    align_nodes,
    apply_geometry_token,
    geometry_token,
    page_box,
    parse_geometry_token,
    reorder_node_z_index,
)
from archium.domain.visual.render_scene import BackgroundStyle, RenderScene, TextNode


def _text_node(
    *,
    node_id: str,
    x: float,
    y: float,
    width: float,
    height: float,
    z_index: int = 1,
) -> TextNode:
    return TextNode(
        id=node_id,
        x=x,
        y=y,
        width=width,
        height=height,
        z_index=z_index,
        text=node_id,
        font_family="Arial",
        font_size=12,
        color="#000000",
        line_height=1.2,
    )


def test_geometry_token_round_trip() -> None:
    node = _text_node(node_id="a", x=1.5, y=2.5, width=3.0, height=4.0)
    token = geometry_token(node)
    assert token == "1.5,2.5,3.0,4.0"
    apply_geometry_token(node, token)
    assert node.x == 1.5
    assert node.height == 4.0


def test_parse_geometry_token_rejects_invalid() -> None:
    with pytest.raises(ValueError, match="invalid geometry token"):
        parse_geometry_token("1,2,3")


def test_align_left_center_right() -> None:
    left = _text_node(node_id="l", x=5, y=1, width=2, height=1)
    center = _text_node(node_id="c", x=8, y=1, width=2, height=1)
    right = _text_node(node_id="r", x=11, y=1, width=2, height=1)
    ref = page_box(20, 10)

    align_nodes([left], "left", reference=ref)
    assert left.x == 0

    align_nodes([center], "center", reference=ref)
    assert center.x == pytest.approx(9.0)

    align_nodes([right], "right", reference=ref)
    assert right.x == pytest.approx(18.0)


def test_align_top_middle_bottom() -> None:
    top = _text_node(node_id="t", x=1, y=5, width=2, height=1)
    middle = _text_node(node_id="m", x=1, y=7, width=2, height=1)
    bottom = _text_node(node_id="b", x=1, y=9, width=2, height=1)
    ref = page_box(20, 10)

    align_nodes([top], "top", reference=ref)
    assert top.y == 0

    align_nodes([middle], "middle", reference=ref)
    assert middle.y == pytest.approx(4.5)

    align_nodes([bottom], "bottom", reference=ref)
    assert bottom.y == pytest.approx(9.0)


def test_distribute_horizontal_and_vertical() -> None:
    nodes = [
        _text_node(node_id="a", x=0, y=0, width=2, height=1),
        _text_node(node_id="b", x=3, y=0, width=2, height=1),
        _text_node(node_id="c", x=10, y=0, width=2, height=1),
    ]
    updates = align_nodes(nodes, "distribute_h")
    assert updates
    assert nodes[1].x > nodes[0].x + nodes[0].width

    vertical = [
        _text_node(node_id="v1", x=0, y=0, width=2, height=1),
        _text_node(node_id="v2", x=0, y=2, width=2, height=1),
        _text_node(node_id="v3", x=0, y=8, width=2, height=1),
    ]
    assert align_nodes(vertical, "distribute_v")


def test_equal_width_and_height() -> None:
    nodes = [
        _text_node(node_id="a", x=0, y=0, width=2, height=1),
        _text_node(node_id="b", x=3, y=0, width=4, height=3),
    ]
    ref = page_box(10, 10)
    align_nodes(nodes, "equal_width", reference=ref)
    assert nodes[0].width == 10
    assert nodes[1].width == 10

    align_nodes(nodes, "equal_height", reference=ref)
    assert nodes[0].height == 10
    assert nodes[1].height == 10


def test_align_returns_empty_for_insufficient_nodes() -> None:
    single = _text_node(node_id="solo", x=1, y=1, width=2, height=1)
    assert align_nodes([], "left") == {}
    assert align_nodes([single], "distribute_h") == {}
    assert align_nodes([single], "equal_width") == {}
    assert align_nodes([single], "left") == {}


def test_reorder_node_z_index_directions() -> None:
    scene = RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=10,
        page_height=5,
        background=BackgroundStyle(color="#FFFFFF"),
        nodes=[
            _text_node(node_id="back", x=0, y=0, width=1, height=1, z_index=1),
            _text_node(node_id="mid", x=1, y=0, width=1, height=1, z_index=3),
            _text_node(node_id="front", x=2, y=0, width=1, height=1, z_index=5),
        ],
    )
    mid = scene.node_by_id("mid")
    assert mid is not None
    assert reorder_node_z_index(scene, mid, "front") == 6
    assert reorder_node_z_index(scene, mid, "back") == 0
    assert reorder_node_z_index(scene, mid, "forward") == 5
    assert reorder_node_z_index(scene, mid, "backward") == 1
