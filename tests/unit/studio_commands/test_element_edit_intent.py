"""Tests for ElementEditIntent parsing and compilation."""

from __future__ import annotations

from uuid import uuid4

from archium.application.visual.comment_to_command_planner import CommentToCommandPlanner
from archium.application.visual.element_edit_intent_compiler import ElementEditIntentCompiler
from archium.application.visual.element_edit_intent_parser import ElementEditIntentParser
from archium.domain.visual.element_comment import ElementComment
from archium.domain.visual.element_edit_intent import ElementEditIntent
from archium.domain.visual.render_scene import BackgroundStyle, ImageNode, RenderScene, TextNode
from archium.domain.visual.studio_command import (
    AlignNodesCommand,
    MoveNodeCommand,
    ReorderNodeCommand,
    ReplaceAssetCommand,
    ResizeNodeCommand,
    RewriteTextCommand,
    SetNodeLockCommand,
    SetNodeVisibilityCommand,
    UpdateNodeStyleCommand,
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


def _image(node_id: str, *, x: float, y: float = 1.0, w: float = 2.0, h: float = 2.0) -> ImageNode:
    return ImageNode(
        id=node_id,
        x=x,
        y=y,
        width=w,
        height=h,
        z_index=1,
        storage_uri=f"project://{node_id}.png",
        asset_path=f"project://{node_id}.png",
    )


def _text(node_id: str, *, x: float = 1.0, y: float = 1.0) -> TextNode:
    return TextNode(
        id=node_id,
        x=x,
        y=y,
        width=3,
        height=0.6,
        z_index=1,
        text="旧文案",
        font_family="Arial",
        font_size=14,
        color="#111111",
        line_height=1.2,
    )


def test_parser_shrink_and_move_keywords() -> None:
    parser = ElementEditIntentParser(use_llm=False)
    scene = _scene(_image("photo", x=4))
    shrink = parser.parse("缩小一点", bound_node_id="photo", scene=scene)
    assert shrink is not None
    assert shrink.operation == "resize"
    assert shrink.direction == "in"
    move = parser.parse("向左移", bound_node_id="photo", scene=scene)
    assert move is not None
    assert move.operation == "move"
    assert move.direction == "left"


def test_parser_align_top_and_center() -> None:
    parser = ElementEditIntentParser(use_llm=False)
    scene = _scene(_image("photo", x=4))
    top = parser.parse("与顶部对齐", bound_node_id="photo", scene=scene)
    assert top is not None
    assert top.operation == "align"
    assert top.direction == "top"
    center = parser.parse("与中心对齐", bound_node_id="photo", scene=scene)
    assert center is not None
    assert center.direction == "center"


def test_parser_rewrite_color_hide_lock_reorder() -> None:
    parser = ElementEditIntentParser(use_llm=False)
    scene = _scene(_text("title"))
    rewrite = parser.parse("改成「新结论」", bound_node_id="title", scene=scene)
    assert rewrite is not None
    assert rewrite.operation == "rewrite_text"
    assert rewrite.text_value == "新结论"

    color = parser.parse("颜色改为 #FF0000", bound_node_id="title", scene=scene)
    assert color is not None
    assert color.operation == "change_style"
    assert color.color_value == "#FF0000"

    hide = parser.parse("隐藏", bound_node_id="title", scene=scene)
    assert hide is not None and hide.visible is False

    unlock = parser.parse("解锁", bound_node_id="title", scene=scene)
    assert unlock is not None and unlock.locked is False

    front = parser.parse("置顶", bound_node_id="title", scene=scene)
    assert front is not None and front.direction == "front"


def test_compiler_move_resize_align_style() -> None:
    compiler = ElementEditIntentCompiler()
    scene = _scene(_image("photo", x=4, y=2), _text("caption", x=1, y=2))
    presentation_id = uuid4()
    slide_id = scene.slide_id

    move_plan = compiler.compile(
        ElementEditIntent(operation="move", direction="left", amount=0.5),
        scene=scene,
        bound_node_id="photo",
        presentation_id=presentation_id,
        slide_id=slide_id,
    )
    assert len(move_plan.commands) == 1
    assert isinstance(move_plan.commands[0], MoveNodeCommand)
    assert move_plan.commands[0].x == 3.5

    shrink_plan = compiler.compile(
        ElementEditIntent(operation="resize", direction="in", amount=0.85),
        scene=scene,
        bound_node_id="photo",
        presentation_id=presentation_id,
        slide_id=slide_id,
    )
    assert isinstance(shrink_plan.commands[0], ResizeNodeCommand)

    align_plan = compiler.compile(
        ElementEditIntent(operation="align", direction="top"),
        scene=scene,
        bound_node_id="photo",
        presentation_id=presentation_id,
        slide_id=slide_id,
    )
    assert isinstance(align_plan.commands[0], MoveNodeCommand)
    assert align_plan.commands[0].y == 0.5

    style_plan = compiler.compile(
        ElementEditIntent(operation="change_style", color_value="#00AA00"),
        scene=scene,
        bound_node_id="caption",
        presentation_id=presentation_id,
        slide_id=slide_id,
    )
    assert isinstance(style_plan.commands[0], UpdateNodeStyleCommand)
    assert style_plan.commands[0].color == "#00AA00"


def test_compiler_match_width_and_replace_asset() -> None:
    compiler = ElementEditIntentCompiler()
    scene = _scene(_image("a", x=1, w=2), _image("b", x=4, w=3))
    presentation_id = uuid4()
    plan = compiler.compile(
        ElementEditIntent(
            operation="resize",
            match_dimension="width",
            reference_node_ids=["b"],
        ),
        scene=scene,
        bound_node_id="a",
        presentation_id=presentation_id,
        slide_id=scene.slide_id,
    )
    assert isinstance(plan.commands[0], ResizeNodeCommand)
    assert plan.commands[0].width == 3.0

    replace = compiler.compile(
        ElementEditIntent(operation="replace_asset", asset_uri="project://new.png"),
        scene=scene,
        bound_node_id="a",
        presentation_id=presentation_id,
        slide_id=scene.slide_id,
    )
    assert isinstance(replace.commands[0], ReplaceAssetCommand)


def test_end_to_end_planner_covers_new_ops() -> None:
    scene = _scene(_text("title", x=2, y=2), _image("photo", x=5, y=2))
    comment = ElementComment(
        presentation_id=uuid4(),
        slide_id=scene.slide_id,
        node_id="title",
        note="隐藏",
    )
    plan = CommentToCommandPlanner(use_llm=False).plan(comment, scene=scene)
    assert len(plan.commands) == 1
    assert isinstance(plan.commands[0], SetNodeVisibilityCommand)
    assert plan.commands[0].visible is False

    comment2 = comment.model_copy(update={"note": "置底", "node_id": "photo"})
    plan2 = CommentToCommandPlanner(use_llm=False).plan(comment2, scene=scene)
    assert isinstance(plan2.commands[0], ReorderNodeCommand)
    assert plan2.commands[0].direction == "back"

    comment3 = comment.model_copy(update={"note": "锁定", "node_id": "title"})
    plan3 = CommentToCommandPlanner(use_llm=False).plan(comment3, scene=scene)
    assert isinstance(plan3.commands[0], SetNodeLockCommand)
    assert plan3.commands[0].locked is True

    comment4 = comment.model_copy(update={"note": "改成新标题", "node_id": "title"})
    plan4 = CommentToCommandPlanner(use_llm=False).plan(comment4, scene=scene)
    assert isinstance(plan4.commands[0], RewriteTextCommand)
    assert plan4.commands[0].new_text == "新标题"


def test_compound_enlarge_and_align_still_works() -> None:
    scene = _scene(_image("photo_left", x=1), _image("photo_right", x=5))
    comment = ElementComment(
        presentation_id=uuid4(),
        slide_id=scene.slide_id,
        node_id="photo_right",
        note="放大一点并和左边对齐",
    )
    plan = CommentToCommandPlanner(use_llm=False).plan(comment, scene=scene)
    assert len(plan.commands) == 2
    assert isinstance(plan.commands[0], ResizeNodeCommand)
    assert isinstance(plan.commands[1], AlignNodesCommand)
