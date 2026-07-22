"""Tests for CommentToCommandPlanner (element-bound NL → StudioCommand)."""

from __future__ import annotations

from uuid import uuid4

from archium.application.visual.comment_to_command_planner import CommentToCommandPlanner
from archium.application.visual.studio_nl_command_planner import StudioNLCommandPlanner
from archium.domain.visual.element_comment import ElementComment
from archium.domain.visual.render_scene import BackgroundStyle, ImageNode, RenderScene, TextNode
from archium.domain.visual.studio_command import (
    AlignNodesCommand,
    ResizeNodeCommand,
    RewriteTextCommand,
)


def _scene(*nodes) -> RenderScene:
    return RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=10,
        page_height=5.625,
        background=BackgroundStyle(color="#FFFFFF"),
        nodes=list(nodes),
    )


def _comment(*, node_id: str, note: str, slide_id=None, presentation_id=None) -> ElementComment:
    return ElementComment(
        presentation_id=presentation_id or uuid4(),
        slide_id=slide_id or uuid4(),
        node_id=node_id,
        note=note,
    )


def test_bound_node_not_overridden_by_title_hint() -> None:
    scene = _scene(
        TextNode(
            id="body",
            semantic_role="body",
            source_layout_element_id="body_el",
            x=1,
            y=2,
            width=4,
            height=1,
            z_index=1,
            text="正文",
            font_family="Arial",
            font_size=14,
            color="#000000",
            line_height=1.2,
        ),
        TextNode(
            id="title",
            semantic_role="title",
            x=1,
            y=0.5,
            width=4,
            height=0.6,
            z_index=2,
            text="旧标题",
            font_family="Arial",
            font_size=24,
            color="#000000",
            line_height=1.2,
        ),
    )
    comment = _comment(node_id="body", note="标题改为新结论", slide_id=scene.slide_id)
    plan = CommentToCommandPlanner().plan(comment, scene=scene)
    assert len(plan.commands) == 1
    command = plan.commands[0]
    assert isinstance(command, RewriteTextCommand)
    assert command.node_id == "body"
    assert "新结论" in command.new_text


def test_enlarge_targets_bound_image_not_default_drawing() -> None:
    scene = _scene(
        ImageNode(
            id="photo_right",
            source_layout_element_id="photo_right_el",
            x=5,
            y=1,
            width=2,
            height=2,
            z_index=1,
            storage_uri="project://a.png",
            asset_path="project://a.png",
        ),
        ImageNode(
            id="photo_left",
            x=1,
            y=1,
            width=2,
            height=2,
            z_index=1,
            storage_uri="project://b.png",
            asset_path="project://b.png",
        ),
    )
    comment = _comment(
        node_id="photo_right",
        note="放大一点",
        slide_id=scene.slide_id,
    )
    plan = CommentToCommandPlanner().plan(comment, scene=scene)
    assert len(plan.commands) == 1
    command = plan.commands[0]
    assert isinstance(command, ResizeNodeCommand)
    assert command.node_id == "photo_right"
    assert command.width > 2.0


def test_enlarge_and_align_left_uses_nearest_left_sibling() -> None:
    scene = _scene(
        ImageNode(
            id="photo_left",
            x=1,
            y=1,
            width=2,
            height=2,
            z_index=1,
            storage_uri="project://b.png",
            asset_path="project://b.png",
        ),
        ImageNode(
            id="photo_right",
            x=5,
            y=1,
            width=2,
            height=2,
            z_index=1,
            storage_uri="project://a.png",
            asset_path="project://a.png",
        ),
    )
    comment = _comment(
        node_id="photo_right",
        note="放大一点并和左边对齐",
        slide_id=scene.slide_id,
    )
    plan = CommentToCommandPlanner().plan(comment, scene=scene)
    assert len(plan.commands) == 2
    assert isinstance(plan.commands[0], ResizeNodeCommand)
    assert plan.commands[0].node_id == "photo_right"
    align = plan.commands[1]
    assert isinstance(align, AlignNodesCommand)
    assert align.node_ids[0] == "photo_right"
    assert align.reference_node_id == "photo_left"
    assert align.alignment == "left"


def test_missing_bound_node_returns_unsupported() -> None:
    scene = _scene(
        TextNode(
            id="title",
            x=1,
            y=1,
            width=4,
            height=0.6,
            z_index=1,
            text="标题",
            font_family="Arial",
            font_size=24,
            color="#000000",
            line_height=1.2,
        )
    )
    comment = _comment(node_id="missing", note="放大一点", slide_id=scene.slide_id)
    plan = CommentToCommandPlanner().plan(comment, scene=scene)
    assert plan.commands == ()
    assert plan.unsupported_reason is not None
    assert "missing" in plan.unsupported_reason


def test_nl_planner_bound_node_id_skips_fuzzy_hint() -> None:
    scene = _scene(
        TextNode(
            id="caption",
            semantic_role="caption",
            x=1,
            y=3,
            width=3,
            height=0.4,
            z_index=1,
            text="图注",
            font_family="Arial",
            font_size=10,
            color="#000000",
            line_height=1.2,
        ),
        TextNode(
            id="title",
            semantic_role="title",
            x=1,
            y=0.5,
            width=4,
            height=0.6,
            z_index=2,
            text="旧标题",
            font_family="Arial",
            font_size=24,
            color="#000000",
            line_height=1.2,
        ),
    )
    plan = StudioNLCommandPlanner().plan_text(
        "标题改为绑定生效",
        scene=scene,
        presentation_id=uuid4(),
        slide_id=scene.slide_id,
        bound_node_id="caption",
    )
    assert len(plan.commands) == 1
    assert isinstance(plan.commands[0], RewriteTextCommand)
    assert plan.commands[0].node_id == "caption"
