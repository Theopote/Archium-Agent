"""Unit tests for GroupNode domain validation and helpers."""

from __future__ import annotations

from uuid import uuid4

import pytest
from archium.domain.visual.render_scene import (
    BackgroundStyle,
    GroupNode,
    RenderScene,
    ShapeNode,
    TextNode,
    compute_group_bounds,
    group_children,
)


def _text(node_id: str, *, x: float = 0.5, y: float = 0.5, group_id: str | None = None) -> TextNode:
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
        group_id=group_id,
    )


def _shape(node_id: str, *, x: float = 1.0, y: float = 1.0, group_id: str | None = None) -> ShapeNode:
    return ShapeNode(
        id=node_id,
        x=x,
        y=y,
        width=1.5,
        height=1.0,
        fill_color="#CCCCCC",
        group_id=group_id,
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


def test_valid_group_round_trips() -> None:
    scene = _scene(
        _text("a", group_id="g1"),
        _shape("b", x=3, y=2, group_id="g1"),
        GroupNode(id="g1", x=0.5, y=0.5, width=4.0, height=2.5, children=["a", "b"]),
    )
    group = scene.node_by_id("g1")
    assert isinstance(group, GroupNode)
    kids = group_children(scene, group)
    assert [node.id for node in kids] == ["a", "b"]
    x, y, w, h = compute_group_bounds(kids)
    assert x == pytest.approx(0.5)
    assert y == pytest.approx(0.5)
    assert w == pytest.approx(4.0)
    assert h == pytest.approx(2.5)


def test_group_rejects_missing_child() -> None:
    with pytest.raises(ValueError, match="missing child"):
        _scene(
            _text("a", group_id="g1"),
            GroupNode(id="g1", x=0.5, y=0.5, width=2.0, height=0.4, children=["a", "ghost"]),
        )


def test_group_rejects_mismatched_group_id() -> None:
    with pytest.raises(ValueError, match="group_id must equal"):
        _scene(
            _text("a", group_id=None),
            _shape("b", group_id="g1"),
            GroupNode(id="g1", x=0.5, y=0.5, width=3.0, height=2.0, children=["a", "b"]),
        )


def test_group_rejects_orphan_group_id() -> None:
    with pytest.raises(ValueError, match="does not reference a GroupNode"):
        _scene(_text("a", group_id="missing"))


def test_group_rejects_self_member() -> None:
    with pytest.raises(ValueError, match="cannot contain itself"):
        _scene(GroupNode(id="g1", x=0, y=0, width=1, height=1, children=["g1"]))


def test_group_rejects_depth_over_max() -> None:
    # Nested chain g5→g4→g3→g2→g1→leaf has depth 5 (> MAX_GROUP_DEPTH=4).
    leaf = _text("leaf", group_id="g1")
    g1 = GroupNode(id="g1", x=0, y=0, width=1, height=1, children=["leaf"], group_id="g2")
    g2 = GroupNode(id="g2", x=0, y=0, width=1, height=1, children=["g1"], group_id="g3")
    g3 = GroupNode(id="g3", x=0, y=0, width=1, height=1, children=["g2"], group_id="g4")
    g4 = GroupNode(id="g4", x=0, y=0, width=1, height=1, children=["g3"], group_id="g5")
    g5 = GroupNode(id="g5", x=0, y=0, width=1, height=1, children=["g4"])
    with pytest.raises(ValueError, match="nesting depth"):
        _scene(leaf, g1, g2, g3, g4, g5)


def test_group_allows_max_depth() -> None:
    leaf = _text("leaf", group_id="g1")
    g1 = GroupNode(id="g1", x=0, y=0, width=1, height=1, children=["leaf"], group_id="g2")
    g2 = GroupNode(id="g2", x=0, y=0, width=1, height=1, children=["g1"], group_id="g3")
    g3 = GroupNode(id="g3", x=0, y=0, width=1, height=1, children=["g2"], group_id="g4")
    g4 = GroupNode(id="g4", x=0, y=0, width=1, height=1, children=["g3"])
    scene = _scene(leaf, g1, g2, g3, g4)
    assert scene.node_by_id("g4") is not None

