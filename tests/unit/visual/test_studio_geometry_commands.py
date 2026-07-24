"""Unit tests for Studio geometry commands and scene edit service."""

from __future__ import annotations

from uuid import uuid4

import pytest
from archium.application.visual.scene_geometry import align_nodes, geometry_token, page_box
from archium.application.visual.scene_proposal_service import apply_patch_actions
from archium.application.visual.studio_command_executor import (
    StudioCommandExecutor,
    StudioExecutionContext,
)
from archium.application.visual.studio_scene_edit_service import sync_layout_geometry_from_scene
from archium.domain.visual.element_lock import ElementLockScope
from archium.domain.visual.enums import LayoutContentType, LayoutElementRole, LayoutFamily
from archium.domain.visual.layout import LayoutElement, LayoutPlan
from archium.domain.visual.render_scene import (
    BackgroundStyle,
    RenderScene,
    TextNode,
)
from archium.domain.visual.studio_command import (
    AlignNodesCommand,
    DeleteNodeCommand,
    MoveNodeCommand,
    ReorderNodeCommand,
    ResizeNodeCommand,
    SetNodeLockCommand,
    SetNodeVisibilityCommand,
    build_patch_action,
)


def _text_node(
    *,
    node_id: str,
    x: float = 1.0,
    y: float = 1.0,
    width: float = 2.0,
    height: float = 0.5,
    source_layout_element_id: str | None = None,
    locked: bool = False,
    visible: bool = True,
    z_index: int = 1,
) -> TextNode:
    return TextNode(
        id=node_id,
        source_layout_element_id=source_layout_element_id or node_id,
        x=x,
        y=y,
        width=width,
        height=height,
        z_index=z_index,
        text="标题",
        font_family="Arial",
        font_size=18,
        color="#000000",
        line_height=1.2,
        locked=locked,
        visible=visible,
    )


def _scene(*nodes: TextNode) -> RenderScene:
    slide_id = uuid4()
    return RenderScene(
        slide_id=slide_id,
        layout_plan_id=uuid4(),
        page_width=10,
        page_height=5.625,
        background=BackgroundStyle(color="#FFFFFF"),
        nodes=list(nodes),
    )


def _context(scene: RenderScene) -> StudioExecutionContext:
    return StudioExecutionContext(presentation_id=uuid4(), slide_order=0)


def test_move_node_updates_geometry_and_patch_replay() -> None:
    scene = _scene(_text_node(node_id="title", x=1.0, y=1.0))
    command = MoveNodeCommand(
        presentation_id=uuid4(),
        slide_id=scene.slide_id,
        node_id="title",
        x=2.5,
        y=3.0,
    )
    result = StudioCommandExecutor().execute(scene, command, _context(scene))
    assert result.success is True
    assert result.candidate_scene is not None
    node = result.candidate_scene.node_by_id("title")
    assert node is not None
    assert node.x == pytest.approx(2.5)
    assert node.y == pytest.approx(3.0)
    assert result.applied_actions
    replayed = apply_patch_actions(scene, list(result.applied_actions))
    replay_node = replayed.node_by_id("title")
    assert replay_node is not None
    assert replay_node.x == pytest.approx(2.5)


def test_resize_node_respects_aspect_ratio() -> None:
    scene = _scene(_text_node(node_id="title", width=2.0, height=1.0))
    command = ResizeNodeCommand(
        presentation_id=uuid4(),
        slide_id=scene.slide_id,
        node_id="title",
        x=1.0,
        y=1.0,
        width=4.0,
        height=4.0,
        preserve_aspect_ratio=True,
    )
    result = StudioCommandExecutor().execute(scene, command, _context(scene))
    assert result.success is True
    assert result.candidate_scene is not None
    node = result.candidate_scene.node_by_id("title")
    assert node is not None
    assert node.width / node.height == pytest.approx(2.0)


def test_delete_node_hides_node() -> None:
    scene = _scene(_text_node(node_id="title"))
    command = DeleteNodeCommand(
        presentation_id=uuid4(),
        slide_id=scene.slide_id,
        node_id="title",
    )
    result = StudioCommandExecutor().execute(scene, command, _context(scene))
    assert result.success is True
    assert result.candidate_scene is not None
    node = result.candidate_scene.node_by_id("title")
    assert node is not None
    assert node.visible is False


def test_duplicate_nodes_clones_with_offset_and_patch_replay() -> None:
    from archium.domain.visual.studio_command import DuplicateNodesCommand

    scene = _scene(_text_node(node_id="title", x=1.0, y=1.0, z_index=2))
    command = DuplicateNodesCommand(
        presentation_id=uuid4(),
        slide_id=scene.slide_id,
        node_ids=["title"],
        new_node_ids=["title__dup_test"],
        offset_x=0.5,
        offset_y=0.25,
    )
    result = StudioCommandExecutor().execute(scene, command, _context(scene))
    assert result.success is True
    assert result.candidate_scene is not None
    assert len(result.candidate_scene.nodes) == 2
    clone = result.candidate_scene.node_by_id("title__dup_test")
    assert clone is not None
    assert clone.x == pytest.approx(1.5)
    assert clone.y == pytest.approx(1.25)
    assert clone.z_index == 3
    assert clone.locked is False
    assert clone.source_layout_element_id == "title__dup_test"
    assert result.applied_actions[0].action_type == "insert_node"

    replayed = apply_patch_actions(scene, list(result.applied_actions))
    assert replayed.node_by_id("title__dup_test") is not None
    assert replayed.node_by_id("title") is not None


def test_sync_layout_recreates_orphan_duplicate_element() -> None:
    from archium.application.visual.studio_scene_edit_service import (
        sync_layout_geometry_from_scene,
    )
    from archium.domain.visual.enums import LayoutContentType, LayoutElementRole
    from archium.domain.visual.layout import LayoutElement, LayoutPlan

    scene = _scene(
        _text_node(node_id="title", x=1.0, y=1.0),
        _text_node(
            node_id="title__dup_a",
            x=1.25,
            y=1.25,
            source_layout_element_id="title__dup_a",
            z_index=5,
        ),
    )
    plan = LayoutPlan(
        slide_id=scene.slide_id,
        layout_family=LayoutFamily.HERO,
        layout_variant="default",
        page_width=10,
        page_height=5.625,
        elements=[
            LayoutElement(
                id="title",
                role=LayoutElementRole.TITLE,
                content_type=LayoutContentType.TEXT,
                text_content="标题",
                x=1.0,
                y=1.0,
                width=2.0,
                height=0.5,
            )
        ],
        reading_order=["title"],
        design_system_id=uuid4(),
        visual_intent_id=uuid4(),
    )
    synced = sync_layout_geometry_from_scene(scene, plan)
    assert {element.id for element in synced.elements} == {"title", "title__dup_a"}
    dup = next(element for element in synced.elements if element.id == "title__dup_a")
    assert dup.x == pytest.approx(1.25)
    assert dup.role == LayoutElementRole.BODY_TEXT


def test_set_node_visibility_updates_visible_state() -> None:
    scene = _scene(_text_node(node_id="title", visible=True))
    command = SetNodeVisibilityCommand(
        presentation_id=uuid4(),
        slide_id=scene.slide_id,
        node_id="title",
        visible=False,
    )
    result = StudioCommandExecutor().execute(scene, command, _context(scene))
    assert result.success is True
    assert result.candidate_scene is not None
    node = result.candidate_scene.node_by_id("title")
    assert node is not None
    assert node.visible is False
    replayed = apply_patch_actions(scene, list(result.applied_actions))
    replay_node = replayed.node_by_id("title")
    assert replay_node is not None
    assert replay_node.visible is False


def test_set_node_visibility_show_restores_hidden_node() -> None:
    scene = _scene(_text_node(node_id="title", visible=False))
    command = SetNodeVisibilityCommand(
        presentation_id=uuid4(),
        slide_id=scene.slide_id,
        node_id="title",
        visible=True,
    )
    result = StudioCommandExecutor().execute(scene, command, _context(scene))
    assert result.success is True
    assert result.candidate_scene is not None
    node = result.candidate_scene.node_by_id("title")
    assert node is not None
    assert node.visible is True


def test_set_node_visibility_works_on_locked_node() -> None:
    scene = _scene(_text_node(node_id="title", locked=True, visible=True))
    command = SetNodeVisibilityCommand(
        presentation_id=uuid4(),
        slide_id=scene.slide_id,
        node_id="title",
        visible=False,
    )
    result = StudioCommandExecutor().execute(scene, command, _context(scene))
    assert result.success is True
    assert result.candidate_scene is not None
    node = result.candidate_scene.node_by_id("title")
    assert node is not None
    assert node.visible is False


def test_reorder_node_forward_moves_to_next_layer() -> None:
    scene = _scene(
        _text_node(node_id="back", z_index=1),
        _text_node(node_id="front", z_index=5),
    )
    command = ReorderNodeCommand(
        presentation_id=uuid4(),
        slide_id=scene.slide_id,
        node_id="back",
        direction="forward",
    )
    result = StudioCommandExecutor().execute(scene, command, _context(scene))
    assert result.success is True
    assert result.candidate_scene is not None
    node = result.candidate_scene.node_by_id("back")
    assert node is not None
    assert node.z_index == 5


def test_reorder_node_front_places_above_all() -> None:
    scene = _scene(
        _text_node(node_id="back", z_index=1),
        _text_node(node_id="front", z_index=5),
    )
    command = ReorderNodeCommand(
        presentation_id=uuid4(),
        slide_id=scene.slide_id,
        node_id="back",
        direction="front",
    )
    result = StudioCommandExecutor().execute(scene, command, _context(scene))
    assert result.success is True
    assert result.candidate_scene is not None
    node = result.candidate_scene.node_by_id("back")
    assert node is not None
    assert node.z_index == 6


def test_reorder_node_works_on_locked_node() -> None:
    scene = _scene(_text_node(node_id="title", z_index=1, locked=True))
    command = ReorderNodeCommand(
        presentation_id=uuid4(),
        slide_id=scene.slide_id,
        node_id="title",
        direction="front",
    )
    result = StudioCommandExecutor().execute(scene, command, _context(scene))
    assert result.success is True
    assert result.candidate_scene is not None
    node = result.candidate_scene.node_by_id("title")
    assert node is not None
    assert node.z_index == 2


def test_reorder_node_patch_replay() -> None:
    scene = _scene(_text_node(node_id="title", z_index=1))
    command = ReorderNodeCommand(
        presentation_id=uuid4(),
        slide_id=scene.slide_id,
        node_id="title",
        direction="front",
    )
    result = StudioCommandExecutor().execute(scene, command, _context(scene))
    assert result.success is True
    replayed = apply_patch_actions(scene, list(result.applied_actions))
    replay_node = replayed.node_by_id("title")
    assert replay_node is not None
    assert replay_node.z_index == 2


def test_set_node_lock_updates_lock_state() -> None:
    scene = _scene(_text_node(node_id="title", locked=False))
    command = SetNodeLockCommand(
        presentation_id=uuid4(),
        slide_id=scene.slide_id,
        node_id="title",
        locked=True,
        lock_scopes=["position", "size"],
    )
    result = StudioCommandExecutor().execute(scene, command, _context(scene))
    assert result.success is True
    assert result.candidate_scene is not None
    node = result.candidate_scene.node_by_id("title")
    assert node is not None
    assert node.locked is True
    assert node.lock_scopes == ["position", "size"]
    replayed = apply_patch_actions(scene, list(result.applied_actions))
    replay_node = replayed.node_by_id("title")
    assert replay_node is not None
    assert replay_node.locked is True
    assert replay_node.lock_scopes == ["position", "size"]


def test_move_node_blocked_after_lock_command() -> None:
    scene = _scene(_text_node(node_id="title", x=1.0, y=1.0))
    lock_result = StudioCommandExecutor().execute(
        scene,
        SetNodeLockCommand(
            presentation_id=uuid4(),
            slide_id=scene.slide_id,
            node_id="title",
            locked=True,
            lock_scopes=["position"],
        ),
        _context(scene),
    )
    assert lock_result.success is True
    assert lock_result.candidate_scene is not None
    move = MoveNodeCommand(
        presentation_id=uuid4(),
        slide_id=scene.slide_id,
        node_id="title",
        x=2.0,
        y=2.0,
    )
    moved = StudioCommandExecutor().execute(lock_result.candidate_scene, move, _context(scene))
    assert moved.success is False
    assert any(issue.code == "STUDIO.NODE_LOCKED" for issue in moved.issues)


def test_align_nodes_uses_page_reference_for_single_node() -> None:
    scene = _scene(_text_node(node_id="title", x=3.0, y=1.0, width=2.0))
    command = AlignNodesCommand(
        presentation_id=uuid4(),
        slide_id=scene.slide_id,
        node_ids=["title"],
        alignment="center",
    )
    result = StudioCommandExecutor().execute(scene, command, _context(scene))
    assert result.success is True
    assert result.candidate_scene is not None
    node = result.candidate_scene.node_by_id("title")
    assert node is not None
    assert node.x == pytest.approx(4.0)


def test_align_nodes_left_with_reference_node() -> None:
    left = _text_node(node_id="caption", x=4.0, y=2.0, width=1.0)
    right = _text_node(node_id="body", x=6.0, y=2.0, width=1.0)
    _scene(left, right)
    updates = align_nodes([right], "left", reference=left)
    assert updates
    assert right.x == pytest.approx(4.0)


def test_align_nodes_equal_width_and_height() -> None:
    a = _text_node(node_id="a", x=1.0, y=1.0, width=2.0, height=0.5)
    b = _text_node(node_id="b", x=4.0, y=1.0, width=3.0, height=1.5)
    updates_w = align_nodes([a, b], "equal_width", reference=a)
    assert updates_w
    assert b.width == pytest.approx(2.0)
    updates_h = align_nodes([a, b], "equal_height", reference=a)
    assert updates_h
    assert b.height == pytest.approx(0.5)


def test_sync_layout_geometry_from_scene() -> None:
    slide_id = uuid4()
    plan = LayoutPlan(
        slide_id=slide_id,
        layout_family=LayoutFamily.HERO,
        layout_variant="centered",
        page_width=10,
        page_height=5.625,
        hero_element_id="title",
        reading_order=["title", "body"],
        whitespace_ratio=0.4,
        elements=[
            LayoutElement(
                id="title",
                role=LayoutElementRole.TITLE,
                content_type=LayoutContentType.TEXT,
                text_content="标题",
                x=1.0,
                y=1.0,
                width=2.0,
                height=0.5,
            ),
            LayoutElement(
                id="body",
                role=LayoutElementRole.BODY_TEXT,
                content_type=LayoutContentType.TEXT,
                text_content="正文",
                x=1.0,
                y=2.0,
                width=3.0,
                height=1.0,
            ),
        ],
        design_system_id=uuid4(),
        visual_intent_id=uuid4(),
    )
    scene = RenderScene(
        slide_id=slide_id,
        layout_plan_id=plan.id,
        page_width=10,
        page_height=5.625,
        background=BackgroundStyle(color="#FFFFFF"),
        nodes=[
            _text_node(node_id="title_node", source_layout_element_id="title", x=2.0, y=2.5),
            _text_node(
                node_id="body_node",
                source_layout_element_id="body",
                x=1.0,
                y=2.0,
                visible=False,
            ),
        ],
    )
    synced = sync_layout_geometry_from_scene(scene, plan)
    title = synced.element_by_id("title")
    assert title is not None
    assert title.x == pytest.approx(2.0)
    assert title.y == pytest.approx(2.5)
    assert synced.element_by_id("body") is None
    assert synced.reading_order == ["title"]
    assert synced.geometry_authority == "render_scene"
    assert synced.synced_scene_version == scene.version


def test_sync_layout_geometry_from_scene_syncs_lock_state() -> None:
    slide_id = uuid4()
    plan = LayoutPlan(
        slide_id=slide_id,
        layout_family=LayoutFamily.HERO,
        layout_variant="centered",
        page_width=10,
        page_height=5.625,
        hero_element_id="title",
        reading_order=["title"],
        whitespace_ratio=0.4,
        elements=[
            LayoutElement(
                id="title",
                role=LayoutElementRole.TITLE,
                content_type=LayoutContentType.TEXT,
                text_content="标题",
                x=1.0,
                y=1.0,
                width=2.0,
                height=0.5,
                locked=False,
            ),
        ],
        design_system_id=uuid4(),
        visual_intent_id=uuid4(),
    )
    scene = RenderScene(
        slide_id=slide_id,
        layout_plan_id=plan.id,
        page_width=10,
        page_height=5.625,
        background=BackgroundStyle(color="#FFFFFF"),
        nodes=[
            _text_node(
                node_id="title_node",
                source_layout_element_id="title",
                locked=True,
            ),
        ],
    )
    scene.nodes[0].lock_scopes = ["position", "size"]
    synced = sync_layout_geometry_from_scene(scene, plan)
    title = synced.element_by_id("title")
    assert title is not None
    assert title.locked is True
    assert title.lock_scopes == [ElementLockScope.POSITION, ElementLockScope.SIZE]


def test_geometry_token_round_trip() -> None:
    node = _text_node(node_id="title", x=1.25, y=2.5, width=3.0, height=0.75)
    token = geometry_token(node)
    action = build_patch_action(
        _scene(node),
        base_scene_hash="hash",
        node_id="title",
        action_type="move_node",
        property_name="geometry",
        before_value="0,0,1,1",
        after_value=token,
    )
    replayed = apply_patch_actions(_scene(_text_node(node_id="title")), [action])
    replay_node = replayed.node_by_id("title")
    assert replay_node is not None
    assert replay_node.x == pytest.approx(1.25)
    assert replay_node.width == pytest.approx(3.0)


def test_page_box_center_alignment() -> None:
    node = _text_node(node_id="title", x=0.0, y=0.0, width=2.0, height=1.0)
    align_nodes([node], "center", reference=page_box(10.0, 5.625))
    assert node.x == pytest.approx(4.0)


def test_update_node_style_changes_text_color_and_font() -> None:
    from archium.domain.visual.studio_command import UpdateNodeStyleCommand

    scene = _scene(_text_node(node_id="title", x=1.0, y=1.0))
    command = UpdateNodeStyleCommand(
        presentation_id=uuid4(),
        slide_id=scene.slide_id,
        target_node_ids=["title"],
        node_id="title",
        color="#E63946",
        font_size=28.0,
    )
    result = StudioCommandExecutor().execute(scene, command, _context(scene))
    assert result.success
    assert result.candidate_scene is not None
    node = result.candidate_scene.node_by_id("title")
    assert isinstance(node, TextNode)
    assert node.color == "#E63946"
    assert node.font_size == pytest.approx(28.0)


def test_update_node_style_shape_fill() -> None:
    from archium.domain.visual.render_scene import ShapeNode
    from archium.domain.visual.studio_command import UpdateNodeStyleCommand

    shape = ShapeNode(
        id="block",
        source_layout_element_id="block",
        x=1.0,
        y=1.0,
        width=2.0,
        height=1.0,
        z_index=1,
        fill_color="#CCCCCC",
    )
    scene = RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=10,
        page_height=5.625,
        background=BackgroundStyle(color="#FFFFFF"),
        nodes=[shape],
    )
    command = UpdateNodeStyleCommand(
        presentation_id=uuid4(),
        slide_id=scene.slide_id,
        target_node_ids=["block"],
        node_id="block",
        fill_color="#112233",
    )
    result = StudioCommandExecutor().execute(scene, command, _context(scene))
    assert result.success
    assert result.candidate_scene is not None
    node = result.candidate_scene.node_by_id("block")
    assert isinstance(node, ShapeNode)
    assert node.fill_color == "#112233"
