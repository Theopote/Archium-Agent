"""Unit tests for StudioCommand protocol and executor."""

from __future__ import annotations

from uuid import uuid4

from archium.application.visual.studio_command_executor import (
    StudioCommandExecutor,
    StudioExecutionContext,
    node_content_locked,
)
from archium.domain.visual.render_scene import BackgroundStyle, RenderScene, TextNode
from archium.domain.visual.studio_command import FixOverflowCommand, RewriteTextCommand


def _text_node(
    *,
    node_id: str,
    text: str,
    locked: bool = False,
    lock_scopes: list[str] | None = None,
    overflow: str = "error",
    x: float = 0.5,
    y: float = 1.0,
    width: float = 2.0,
    height: float = 0.4,
) -> TextNode:
    return TextNode(
        id=node_id,
        x=x,
        y=y,
        width=width,
        height=height,
        z_index=1,
        text=text,
        font_family="Arial",
        font_size=12,
        color="#000000",
        line_height=1.2,
        overflow_policy=overflow,
        locked=locked,
        lock_scopes=list(lock_scopes or []),
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


def test_rewrite_text_updates_node_and_paragraphs() -> None:
    scene = _scene(
        _text_node(
            node_id="title",
            text="旧标题",
        )
    )
    scene.nodes[0].paragraphs = [{"text": "旧标题", "alignment": "left"}]
    command = RewriteTextCommand(
        presentation_id=uuid4(),
        slide_id=scene.slide_id,
        node_id="title",
        new_text="结论式标题：院区交通组织优化",
        reason="convert title to claim",
    )
    result = StudioCommandExecutor().execute(scene, command, _context(scene))
    assert result.success is True
    assert result.candidate_scene is not None
    node = result.candidate_scene.node_by_id("title")
    assert isinstance(node, TextNode)
    assert node.text == "结论式标题：院区交通组织优化"
    assert node.paragraphs[0].text == "结论式标题：院区交通组织优化"
    assert len(result.applied_actions) == 1
    assert result.applied_actions[0].action_type == "rewrite_text"
    assert result.applied_actions[0].before_value == "旧标题"


def test_rewrite_text_rejects_locked_node() -> None:
    scene = _scene(_text_node(node_id="body", text="正文", locked=True))
    command = RewriteTextCommand(
        presentation_id=uuid4(),
        slide_id=scene.slide_id,
        node_id="body",
        new_text="新正文",
    )
    result = StudioCommandExecutor().execute(scene, command, _context(scene))
    assert result.success is False
    assert result.candidate_scene is None
    assert any("locked" in item for item in result.skipped_actions)


def test_rewrite_text_rejects_non_text_node() -> None:
    from archium.domain.visual.render_scene import ShapeNode

    scene = RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=10,
        page_height=5.625,
        background=BackgroundStyle(color="#FFFFFF"),
        nodes=[
            ShapeNode(
                id="card",
                x=1,
                y=1,
                width=2,
                height=1,
                fill_color="#EEEEEE",
            )
        ],
    )
    command = RewriteTextCommand(
        presentation_id=uuid4(),
        slide_id=scene.slide_id,
        node_id="card",
        new_text="不可能",
    )
    result = StudioCommandExecutor().execute(scene, command, _context(scene))
    assert result.success is False
    assert any(issue.code == "STUDIO.NODE_NOT_TEXT" for issue in result.issues)


def test_node_content_locked_respects_scopes() -> None:
    node = _text_node(node_id="n", text="x", lock_scopes=["content"])
    assert node_content_locked(node) is True
    node = _text_node(node_id="n", text="x", lock_scopes=["position"])
    assert node_content_locked(node) is False


def test_fix_overflow_shortens_long_text() -> None:
    long_text = "这是一段非常长的说明文字，用于验证溢出修复。" * 15
    scene = _scene(_text_node(node_id="body_1", text=long_text, width=1.5, height=0.3))
    command = FixOverflowCommand(
        presentation_id=uuid4(),
        slide_id=scene.slide_id,
        reason="fix body overflow",
    )
    result = StudioCommandExecutor().execute(scene, command, _context(scene))
    assert result.success is True
    assert result.candidate_scene is not None
    node = result.candidate_scene.node_by_id("body_1")
    assert isinstance(node, TextNode)
    assert len(node.text) < len(long_text)
    assert result.applied_actions


def test_fix_overflow_skips_locked_nodes() -> None:
    long_text = "锁定节点不应被自动缩短。" * 20
    scene = _scene(
        _text_node(node_id="locked_body", text=long_text, locked=True, width=1.5, height=0.3)
    )
    command = FixOverflowCommand(
        presentation_id=uuid4(),
        slide_id=scene.slide_id,
        node_ids=["locked_body"],
    )
    result = StudioCommandExecutor().execute(scene, command, _context(scene))
    assert result.success is False
    assert any("locked" in item for item in result.skipped_actions)


def test_fix_overflow_no_issue_is_noop() -> None:
    scene = _scene(_text_node(node_id="short", text="短文本"))
    command = FixOverflowCommand(
        presentation_id=uuid4(),
        slide_id=scene.slide_id,
    )
    result = StudioCommandExecutor().execute(scene, command, _context(scene))
    assert result.success is True
    assert result.applied_actions == ()
    assert result.candidate_scene is not None


def test_fix_overflow_filters_by_node_ids() -> None:
    long_text = "溢出正文" * 30
    scene = _scene(
        _text_node(node_id="overflow_a", text=long_text, width=1.2, height=0.25),
        _text_node(node_id="overflow_b", text=long_text, width=1.2, height=0.25, y=2.0),
    )
    command = FixOverflowCommand(
        presentation_id=uuid4(),
        slide_id=scene.slide_id,
        node_ids=["overflow_a"],
    )
    result = StudioCommandExecutor().execute(scene, command, _context(scene))
    assert result.success is True
    node_a = result.candidate_scene.node_by_id("overflow_a") if result.candidate_scene else None
    node_b = result.candidate_scene.node_by_id("overflow_b") if result.candidate_scene else None
    assert isinstance(node_a, TextNode)
    assert isinstance(node_b, TextNode)
    assert len(node_a.text) < len(long_text)
    assert node_b.text == long_text
