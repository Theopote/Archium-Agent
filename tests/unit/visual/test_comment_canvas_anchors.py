"""Tests for comment canvas anchors and snapshot diff."""

from __future__ import annotations

from uuid import uuid4

from archium.domain.visual.element_comment import (
    ElementComment,
    ElementCommentScope,
    ElementCommentStatus,
)
from archium.domain.visual.render_scene import BackgroundStyle, RenderScene, TextNode
from archium.ui.studio.comment_canvas_anchors import (
    build_comment_canvas_anchors,
    canvas_element_id_for_node,
    comment_snapshot_diff,
)


def _scene() -> RenderScene:
    return RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=10.0,
        page_height=5.0,
        background=BackgroundStyle(color="#FFFFFF"),
        nodes=[
            TextNode(
                id="node-a",
                source_layout_element_id="el-a",
                x=1.0,
                y=0.5,
                width=2.0,
                height=1.0,
                z_index=1,
                text="A",
                font_family="Arial",
                font_size=12,
                color="#000000",
                line_height=16,
            ),
            TextNode(
                id="node-b",
                source_layout_element_id="el-b",
                x=4.0,
                y=2.0,
                width=2.0,
                height=1.0,
                z_index=2,
                text="B",
                font_family="Arial",
                font_size=12,
                color="#000000",
                line_height=16,
            ),
        ],
    )


def test_canvas_element_id_maps_layout_source() -> None:
    scene = _scene()
    assert canvas_element_id_for_node(scene, "node-a") == "el-a"
    assert canvas_element_id_for_node(None, "node-a") == "node-a"


def test_build_node_and_region_anchors_in_percent() -> None:
    scene = _scene()
    node_comment = ElementComment(
        presentation_id=uuid4(),
        slide_id=scene.slide_id,
        node_id="node-a",
        layout_element_id="el-a",
        note="放大一点",
        status=ElementCommentStatus.PENDING,
    )
    region_comment = ElementComment(
        presentation_id=node_comment.presentation_id,
        slide_id=scene.slide_id,
        node_id="node-b",
        note="对齐选区",
        status=ElementCommentStatus.PROPOSED,
        scope=ElementCommentScope.REGION,
        region_bbox={"x": 1.0, "y": 0.5, "width": 5.0, "height": 2.5},
    )
    anchors = build_comment_canvas_anchors(
        [node_comment, region_comment],
        page_width=10.0,
        page_height=5.0,
        scene=scene,
        focused_comment_id=region_comment.id,
    )
    assert len(anchors) == 2
    pin = next(a for a in anchors if a["kind"] == "node")
    # pin at top-right of node-a: x=(1+2)/10*100=30, y=0.5/5*100=10
    assert abs(pin["x"] - 30.0) < 1e-6
    assert abs(pin["y"] - 10.0) < 1e-6
    region = next(a for a in anchors if a["kind"] == "region")
    assert region["focused"] is True
    assert abs(region["x"] - 10.0) < 1e-6
    assert abs(region["width"] - 50.0) < 1e-6
    assert abs(region["height"] - 50.0) < 1e-6


def test_comment_snapshot_diff_reports_geometry_change() -> None:
    scene = _scene()
    node = scene.node_by_id("node-a")
    assert node is not None
    snapshot = node.model_dump(mode="json")
    snapshot["x"] = 0.0
    snapshot["text"] = "旧标题"
    comment = ElementComment(
        presentation_id=uuid4(),
        slide_id=scene.slide_id,
        node_id="node-a",
        note="改标题",
        status=ElementCommentStatus.NEEDS_REBASE,
        node_snapshot_json=snapshot,
    )
    rows = {key: (old, new) for key, old, new in comment_snapshot_diff(comment, scene=scene)}
    assert rows["x"] == (0.0, 1.0)
    assert rows["text"] == ("旧标题", "A")
