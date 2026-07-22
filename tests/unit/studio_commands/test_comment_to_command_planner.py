"""Tests for CommentToCommandPlanner (element-bound NL → StudioCommand)."""

from __future__ import annotations

from uuid import uuid4

from archium.application.visual.comment_to_command_planner import CommentToCommandPlanner
from archium.application.visual.studio_nl_command_planner import StudioNLCommandPlanner
from archium.domain.visual.element_comment import ElementComment, ElementCommentScope
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


def _comment(
    *,
    node_id: str,
    note: str,
    slide_id=None,
    presentation_id=None,
    scope: ElementCommentScope = ElementCommentScope.NODE,
    scope_node_ids: list[str] | None = None,
) -> ElementComment:
    return ElementComment(
        presentation_id=presentation_id or uuid4(),
        slide_id=slide_id or uuid4(),
        node_id=node_id,
        note=note,
        scope=scope,
        scope_node_ids=list(scope_node_ids or []),
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


def test_multi_node_note_with_default_scope_is_gated() -> None:
    scene = _scene(
        ImageNode(
            id="card_a",
            x=1,
            y=1,
            width=2,
            height=2,
            z_index=1,
            storage_uri="project://a.png",
            asset_path="project://a.png",
        )
    )
    comment = _comment(
        node_id="card_a",
        note="让这三个卡片大小一致",
        slide_id=scene.slide_id,
    )
    plan = CommentToCommandPlanner().plan(comment, scene=scene)
    assert plan.commands == ()
    assert plan.unsupported_reason is not None
    assert "selection" in plan.unsupported_reason
    assert CommentToCommandPlanner.suggested_scope_for_note(comment.note) == (
        ElementCommentScope.SELECTION
    )


def test_selection_scope_allows_multi_node_targets() -> None:
    scene = _scene(
        ImageNode(
            id="card_a",
            x=1,
            y=1,
            width=2,
            height=1.5,
            z_index=1,
            storage_uri="project://a.png",
            asset_path="project://a.png",
        ),
        ImageNode(
            id="card_b",
            x=4,
            y=1,
            width=2.5,
            height=2,
            z_index=1,
            storage_uri="project://b.png",
            asset_path="project://b.png",
        ),
        ImageNode(
            id="card_c",
            x=7,
            y=1,
            width=1.8,
            height=2.2,
            z_index=1,
            storage_uri="project://c.png",
            asset_path="project://c.png",
        ),
    )
    presentation_id = uuid4()
    commands = []
    for node_id, width, height in (
        ("card_a", 2.0, 2.0),
        ("card_b", 2.0, 2.0),
        ("card_c", 2.0, 2.0),
    ):
        node = scene.node_by_id(node_id)
        assert node is not None
        commands.append(
            ResizeNodeCommand(
                presentation_id=presentation_id,
                slide_id=scene.slide_id,
                node_id=node_id,
                target_node_ids=[node_id],
                x=node.x,
                y=node.y,
                width=width,
                height=height,
                reason="equalize",
                expected_effect=f"统一 `{node_id}` 尺寸",
            )
        )

    class _StubNL:
        def plan_text(self, *args, **kwargs):  # noqa: ANN002, ANN003
            from archium.application.visual.studio_nl_command_planner import StudioCommandPlan

            return StudioCommandPlan(commands=tuple(commands), reasons=("equalize cards",))

    comment = _comment(
        node_id="card_a",
        note="让这三个卡片大小一致",
        slide_id=scene.slide_id,
        presentation_id=presentation_id,
        scope=ElementCommentScope.SELECTION,
        scope_node_ids=["card_b", "card_c"],
    )
    plan = CommentToCommandPlanner(nl_planner=_StubNL()).plan(comment, scene=scene)
    assert len(plan.commands) == 3
    assert {cmd.node_id for cmd in plan.commands} == {"card_a", "card_b", "card_c"}


def test_selection_scope_rejects_outside_targets() -> None:
    scene = _scene(
        ImageNode(
            id="card_a",
            x=1,
            y=1,
            width=2,
            height=2,
            z_index=1,
            storage_uri="project://a.png",
            asset_path="project://a.png",
        ),
        ImageNode(
            id="card_b",
            x=4,
            y=1,
            width=2,
            height=2,
            z_index=1,
            storage_uri="project://b.png",
            asset_path="project://b.png",
        ),
        ImageNode(
            id="outsider",
            x=7,
            y=1,
            width=2,
            height=2,
            z_index=1,
            storage_uri="project://c.png",
            asset_path="project://c.png",
        ),
    )
    presentation_id = uuid4()

    class _StubNL:
        def plan_text(self, *args, **kwargs):  # noqa: ANN002, ANN003
            from archium.application.visual.studio_nl_command_planner import StudioCommandPlan

            return StudioCommandPlan(
                commands=(
                    ResizeNodeCommand(
                        presentation_id=presentation_id,
                        slide_id=scene.slide_id,
                        node_id="outsider",
                        target_node_ids=["outsider"],
                        x=7,
                        y=1,
                        width=2,
                        height=2,
                        reason="leak",
                        expected_effect="改到作用域外",
                    ),
                ),
                reasons=("leak",),
            )

    comment = _comment(
        node_id="card_a",
        note="统一大小",
        slide_id=scene.slide_id,
        presentation_id=presentation_id,
        scope=ElementCommentScope.SELECTION,
        scope_node_ids=["card_b"],
    )
    plan = CommentToCommandPlanner(nl_planner=_StubNL()).plan(comment, scene=scene)
    assert plan.commands == ()
    assert plan.unsupported_reason is not None
    assert "outsider" in plan.unsupported_reason


def test_node_and_references_keeps_align_reference() -> None:
    scene = _scene(
        TextNode(
            id="caption",
            x=1,
            y=2,
            width=2,
            height=0.5,
            z_index=1,
            text="说明",
            font_family="Arial",
            font_size=12,
            color="#000000",
            line_height=1.2,
        ),
        ImageNode(
            id="photo",
            x=4,
            y=1,
            width=3,
            height=3,
            z_index=1,
            storage_uri="project://a.png",
            asset_path="project://a.png",
        ),
    )
    comment = _comment(
        node_id="photo",
        note="和左边对齐",
        slide_id=scene.slide_id,
        scope=ElementCommentScope.NODE_AND_REFERENCES,
    )
    plan = CommentToCommandPlanner().plan(comment, scene=scene)
    assert len(plan.commands) == 1
    align = plan.commands[0]
    assert isinstance(align, AlignNodesCommand)
    assert align.node_ids[0] == "photo"
    assert "caption" in align.node_ids
