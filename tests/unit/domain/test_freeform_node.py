"""FreeformNode domain validation and geometry helpers."""

from __future__ import annotations

from uuid import uuid4

import pytest
from archium.domain.visual.render_scene import (
    BackgroundStyle,
    FreeformNode,
    Point,
    RenderScene,
    compute_freeform_bounds,
    freeform_preset_points,
    is_polygon_convex,
    move_freeform_to,
    refresh_freeform_geometry,
    resize_freeform_to,
)
from pydantic import ValidationError


def _scene(*nodes: object) -> RenderScene:
    return RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=10,
        page_height=5.625,
        background=BackgroundStyle(color="#FFFFFF"),
        nodes=list(nodes),  # type: ignore[arg-type]
    )


def test_freeform_requires_three_points() -> None:
    with pytest.raises(ValidationError):
        FreeformNode(
            id="ff1",
            x=0,
            y=0,
            width=1,
            height=1,
            points=[Point(x=0, y=0), Point(x=1, y=0)],
        )


def test_triangle_preset_is_convex() -> None:
    points = freeform_preset_points("triangle", x=1, y=1, width=2, height=2)
    assert len(points) == 3
    assert is_polygon_convex(points) is True
    x, y, w, h = compute_freeform_bounds(points)
    assert x == pytest.approx(1.0)
    assert y == pytest.approx(1.0)
    assert w == pytest.approx(2.0)
    assert h == pytest.approx(2.0)


def test_move_and_resize_keep_points_in_sync() -> None:
    points = freeform_preset_points("diamond", x=2, y=1, width=2, height=2)
    node = FreeformNode(
        id="ff1",
        x=2,
        y=1,
        width=2,
        height=2,
        points=points,
    )
    refresh_freeform_geometry(node)
    move_freeform_to(node, x=4, y=2)
    assert node.x == pytest.approx(4.0)
    assert node.y == pytest.approx(2.0)
    assert min(p.x for p in node.points) == pytest.approx(4.0)

    resize_freeform_to(node, x=4, y=2, width=4, height=3)
    assert node.width == pytest.approx(4.0)
    assert node.height == pytest.approx(3.0)
    assert len(node.points) == 4


def test_scene_accepts_freeform_node() -> None:
    points = freeform_preset_points("rect_zone", x=0.5, y=0.5, width=1, height=1)
    node = FreeformNode(
        id="ff1",
        x=0.5,
        y=0.5,
        width=1,
        height=1,
        points=points,
        fill_color="#E8F0FE",
    )
    scene = _scene(node)
    assert scene.node_by_id("ff1") is node
