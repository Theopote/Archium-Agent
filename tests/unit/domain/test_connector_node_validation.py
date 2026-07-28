"""Unit tests for ConnectorNode domain helpers and validation."""

from __future__ import annotations

from uuid import uuid4

import pytest
from archium.domain.visual.render_scene import (
    BackgroundStyle,
    ConnectorEndpoint,
    ConnectorNode,
    RenderScene,
    ShapeNode,
    TextNode,
    connector_path_points,
    refresh_connector_geometry,
    resolve_anchor_point,
)


def _shape(node_id: str, *, x: float, y: float, w: float = 1.0, h: float = 1.0) -> ShapeNode:
    return ShapeNode(
        id=node_id,
        x=x,
        y=y,
        width=w,
        height=h,
        fill_color="#DDDDDD",
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


def test_resolve_anchor_points() -> None:
    node = _shape("a", x=1.0, y=2.0, w=2.0, h=1.0)
    assert resolve_anchor_point(node, ConnectorEndpoint(node_id="a", anchor="center")) == (
        2.0,
        2.5,
    )
    assert resolve_anchor_point(node, ConnectorEndpoint(node_id="a", anchor="right")) == (
        3.0,
        2.5,
    )
    assert resolve_anchor_point(node, ConnectorEndpoint(node_id="a", anchor="top")) == (
        2.0,
        2.0,
    )


def test_valid_connector_and_refresh() -> None:
    a = _shape("a", x=1.0, y=1.0)
    b = _shape("b", x=4.0, y=3.0)
    cxn = ConnectorNode(
        id="c1",
        x=0.05,
        y=0.05,
        width=0.05,
        height=0.05,
        start=ConnectorEndpoint(node_id="a", anchor="right"),
        end=ConnectorEndpoint(node_id="b", anchor="left"),
    )
    scene = _scene(a, b, cxn)
    live = scene.node_by_id("c1")
    assert isinstance(live, ConnectorNode)
    assert refresh_connector_geometry(scene, live) is True
    assert live.x == pytest.approx(2.0)
    assert live.y == pytest.approx(1.5)
    assert live.width == pytest.approx(2.0)
    assert live.height == pytest.approx(2.0)


def test_elbow_path_has_mid_points() -> None:
    a = _shape("a", x=0.0, y=0.0)
    b = _shape("b", x=4.0, y=2.0)
    cxn = ConnectorNode(
        id="c1",
        x=0.05,
        y=0.05,
        width=0.05,
        height=0.05,
        routing="elbow",
        start=ConnectorEndpoint(node_id="a", anchor="center"),
        end=ConnectorEndpoint(node_id="b", anchor="center"),
    )
    scene = _scene(a, b, cxn)
    refresh_connector_geometry(scene, cxn)
    points = connector_path_points(scene, cxn)
    assert len(points) == 4


def test_connector_rejects_missing_endpoint() -> None:
    with pytest.raises(ValueError, match="missing node"):
        _scene(
            _shape("a", x=0, y=0),
            ConnectorNode(
                id="c1",
                x=0.05,
                y=0.05,
                width=0.05,
                height=0.05,
                start=ConnectorEndpoint(node_id="a"),
                end=ConnectorEndpoint(node_id="ghost"),
            ),
        )


def test_connector_rejects_same_endpoint() -> None:
    with pytest.raises(ValueError, match="must differ"):
        _scene(
            _shape("a", x=0, y=0),
            ConnectorNode(
                id="c1",
                x=0.05,
                y=0.05,
                width=0.05,
                height=0.05,
                start=ConnectorEndpoint(node_id="a"),
                end=ConnectorEndpoint(node_id="a"),
            ),
        )


def test_connector_rejects_connector_target() -> None:
    a = _shape("a", x=0, y=0)
    b = _shape("b", x=2, y=0)
    c1 = ConnectorNode(
        id="c1",
        x=0.05,
        y=0.05,
        width=0.05,
        height=0.05,
        start=ConnectorEndpoint(node_id="a"),
        end=ConnectorEndpoint(node_id="b"),
    )
    with pytest.raises(ValueError, match="another connector"):
        _scene(
            a,
            b,
            c1,
            ConnectorNode(
                id="c2",
                x=0.05,
                y=0.05,
                width=0.05,
                height=0.05,
                start=ConnectorEndpoint(node_id="c1"),
                end=ConnectorEndpoint(node_id="a"),
            ),
        )


def test_text_can_be_endpoint() -> None:
    title = TextNode(
        id="t",
        x=1,
        y=1,
        width=2,
        height=0.5,
        text="A",
        font_family="Arial",
        font_size=14,
        color="#000",
        line_height=1.2,
    )
    shape = _shape("s", x=4, y=2)
    cxn = ConnectorNode(
        id="c1",
        x=0.05,
        y=0.05,
        width=0.05,
        height=0.05,
        start=ConnectorEndpoint(node_id="t", anchor="bottom"),
        end=ConnectorEndpoint(node_id="s", anchor="top"),
    )
    scene = _scene(title, shape, cxn)
    assert scene.node_by_id("c1") is not None
