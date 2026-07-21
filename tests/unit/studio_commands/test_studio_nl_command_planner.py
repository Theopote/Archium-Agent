"""Tests for NL → StudioCommand planning."""

from __future__ import annotations

from uuid import uuid4

import pytest
from archium.application.visual.studio_nl_command_planner import (
    StudioNLCommandPlanner,
    resolve_render_node_id,
)
from archium.domain.visual.edit_intent import VisualEditIntent
from archium.domain.visual.render_scene import BackgroundStyle, RenderScene, TextNode
from archium.domain.visual.studio_command import FixOverflowCommand, RewriteTextCommand


def _scene(*nodes: TextNode) -> RenderScene:
    return RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=10,
        page_height=5.625,
        background=BackgroundStyle(color="#FFFFFF"),
        nodes=list(nodes),
    )


def _title_scene() -> RenderScene:
    return _scene(
        TextNode(
            id="title",
            semantic_role="title",
            x=1,
            y=1,
            width=4,
            height=0.6,
            z_index=1,
            text="旧标题",
            font_family="Arial",
            font_size=24,
            color="#000000",
            line_height=1.2,
        )
    )


def test_plan_rewrite_title_pattern() -> None:
    scene = _title_scene()
    presentation_id = uuid4()
    slide_id = scene.slide_id
    plan = StudioNLCommandPlanner().plan_text(
        "标题改为结论：院区交通需分层组织",
        scene=scene,
        presentation_id=presentation_id,
        slide_id=slide_id,
    )
    assert len(plan.commands) == 1
    command = plan.commands[0]
    assert isinstance(command, RewriteTextCommand)
    assert command.node_id == "title"
    assert "结论" in command.new_text


def test_plan_reduce_text_maps_to_fix_overflow() -> None:
    scene = _title_scene()
    presentation_id = uuid4()
    plan = StudioNLCommandPlanner().plan_text(
        "减少文字",
        scene=scene,
        presentation_id=presentation_id,
        slide_id=scene.slide_id,
    )
    assert len(plan.commands) == 1
    assert isinstance(plan.commands[0], FixOverflowCommand)


def test_plan_enlarge_hero_maps_to_drawing_readability_when_drawing_exists() -> None:
    from archium.domain.visual.render_scene import DrawingNode

    scene = RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=10,
        page_height=5.625,
        background=BackgroundStyle(color="#FFFFFF"),
        nodes=[
            DrawingNode(
                id="site_plan",
                x=1,
                y=1,
                width=3,
                height=2,
                z_index=1,
                storage_uri="project://plan.png",
                asset_path="project://plan.png",
            )
        ],
    )
    plan = StudioNLCommandPlanner().plan_text(
        "放大主图",
        scene=scene,
        presentation_id=uuid4(),
        slide_id=scene.slide_id,
    )
    assert len(plan.commands) == 1
    from archium.domain.visual.studio_command import IncreaseDrawingReadabilityCommand

    assert isinstance(plan.commands[0], IncreaseDrawingReadabilityCommand)


def test_plan_drawing_readability_keywords() -> None:
    from archium.domain.visual.render_scene import DrawingNode

    scene = RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=10,
        page_height=5.625,
        background=BackgroundStyle(color="#FFFFFF"),
        nodes=[
            DrawingNode(
                id="site_plan",
                x=1,
                y=1,
                width=3,
                height=2,
                z_index=1,
                storage_uri="project://plan.png",
                asset_path="project://plan.png",
            )
        ],
    )
    plan = StudioNLCommandPlanner().plan_text(
        "提高图纸可读性",
        scene=scene,
        presentation_id=uuid4(),
        slide_id=scene.slide_id,
    )
    assert plan.commands


def test_plan_enlarge_hero_marks_layout_fallback_without_drawing() -> None:
    scene = _title_scene()
    plan = StudioNLCommandPlanner().plan_text(
        "放大主图",
        scene=scene,
        presentation_id=uuid4(),
        slide_id=scene.slide_id,
    )
    assert not plan.commands
    assert plan.uses_layout_fallback is True
    assert plan.parsed_intent == VisualEditIntent.ENLARGE_HERO


def test_resolve_render_node_id_by_alias() -> None:
    scene = _scene(
        TextNode(
            id="node_body",
            semantic_role="body",
            x=1,
            y=2,
            width=4,
            height=1,
            z_index=1,
            text="正文",
            font_family="Arial",
            font_size=12,
            color="#000000",
            line_height=1.2,
        )
    )
    assert resolve_render_node_id(scene, "正文") == "node_body"


def test_plan_element_specific_rewrite() -> None:
    scene = _scene(
        TextNode(
            id="body",
            x=1,
            y=2,
            width=4,
            height=1,
            z_index=1,
            text="旧正文",
            font_family="Arial",
            font_size=12,
            color="#000000",
            line_height=1.2,
        )
    )
    plan = StudioNLCommandPlanner().plan_text(
        "把正文改成更新后的说明",
        scene=scene,
        presentation_id=uuid4(),
        slide_id=scene.slide_id,
    )
    command = plan.commands[0]
    assert isinstance(command, RewriteTextCommand)
    assert command.node_id == "body"
    assert command.new_text == "更新后的说明"


def test_resolve_missing_node_raises() -> None:
    scene = _title_scene()
    with pytest.raises(ValueError):
        resolve_render_node_id(scene, "missing_element")
