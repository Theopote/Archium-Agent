"""Unit tests for StudioCommand protocol and executor."""

from __future__ import annotations

from uuid import UUID, uuid4

from archium.application.visual.asset_path_resolver import (
    AssetPathResolveContext,
    benchmark_asset_uri,
    project_asset_uri,
)
from archium.application.visual.studio_command_executor import (
    StudioCommandExecutor,
    StudioExecutionContext,
    node_asset_locked,
    node_content_locked,
)
from archium.domain.visual.render_scene import (
    BackgroundStyle,
    DrawingNode,
    ImageNode,
    RenderNode,
    RenderScene,
    TextNode,
)
from archium.domain.visual.studio_command import (
    FixOverflowCommand,
    ReplaceAssetCommand,
    ReplaceDrawingCommand,
    RewriteTextCommand,
)


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


def _render_scene(*nodes: RenderNode) -> RenderScene:
    slide_id = uuid4()
    return RenderScene(
        slide_id=slide_id,
        layout_plan_id=uuid4(),
        page_width=10,
        page_height=5.625,
        background=BackgroundStyle(color="#FFFFFF"),
        nodes=list(nodes),
    )


def _scene(*nodes: TextNode) -> RenderScene:
    return _render_scene(*nodes)


def _context(
    scene: RenderScene,
    *,
    validate_asset_bindings: bool = False,
    asset_resolve_context: AssetPathResolveContext | None = None,
) -> StudioExecutionContext:
    return StudioExecutionContext(
        presentation_id=uuid4(),
        validate_asset_bindings=validate_asset_bindings,
        asset_resolve_context=asset_resolve_context,
    )


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
    assert len(node.paragraphs) == 1
    assert node.paragraphs[0].text == "结论式标题：院区交通组织优化"
    assert len(result.applied_actions) == 1
    assert result.applied_actions[0].action_type == "rewrite_text"
    assert result.applied_actions[0].before_value == "旧标题"
    action = result.applied_actions[0]
    assert action.scene_id == scene.id
    assert action.slide_id == scene.slide_id
    assert action.scene_id != action.slide_id
    assert action.base_scene_hash == result.base_scene_hash


def test_rewrite_text_replaces_all_paragraphs() -> None:
    scene = _scene(_text_node(node_id="body", text="第一段\n第二段\n第三段"))
    text_node = scene.nodes[0]
    text_node.paragraphs = [
        {"text": "第一段", "alignment": "left"},
        {"text": "第二段", "alignment": "left"},
        {"text": "第三段", "alignment": "left"},
    ]
    command = RewriteTextCommand(
        presentation_id=uuid4(),
        slide_id=scene.slide_id,
        node_id="body",
        new_text="合并后的新正文",
    )
    result = StudioCommandExecutor().execute(scene, command, _context(scene))
    assert result.success is True
    node = result.candidate_scene.node_by_id("body") if result.candidate_scene else None
    assert isinstance(node, TextNode)
    assert node.text == "合并后的新正文"
    assert len(node.paragraphs) == 1
    assert node.paragraphs[0].text == "合并后的新正文"
    assert all(paragraph.text == "合并后的新正文" for paragraph in node.paragraphs)


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


def _image_node(
    *,
    node_id: str,
    asset_id: UUID | None = None,
    storage_uri: str = "project://old-photo.png",
    locked: bool = False,
    lock_scopes: list[str] | None = None,
) -> ImageNode:
    resolved_id = asset_id or uuid4()
    return ImageNode(
        id=node_id,
        x=1.0,
        y=1.0,
        width=4.0,
        height=3.0,
        z_index=2,
        asset_id=resolved_id,
        storage_uri=storage_uri,
        asset_path=storage_uri,
        asset_origin="project_upload",
        fit_mode="cover",
        locked=locked,
        lock_scopes=list(lock_scopes or []),
    )


def _drawing_node(
    *,
    node_id: str,
    asset_id: UUID | None = None,
    storage_uri: str = "project://old-plan.png",
    locked: bool = False,
) -> DrawingNode:
    resolved_id = asset_id or uuid4()
    return DrawingNode(
        id=node_id,
        x=0.5,
        y=0.5,
        width=8.0,
        height=4.5,
        z_index=1,
        asset_id=resolved_id,
        storage_uri=storage_uri,
        asset_path=storage_uri,
        drawing_type="site_plan",
        fit_mode="contain",
        locked=locked,
    )


def test_replace_asset_updates_image_node_and_manifest() -> None:
    old_id = uuid4()
    new_id = uuid4()
    scene = _render_scene(_image_node(node_id="photo_1", asset_id=old_id))
    command = ReplaceAssetCommand(
        presentation_id=uuid4(),
        slide_id=scene.slide_id,
        node_id="photo_1",
        asset_id=new_id,
        storage_uri=project_asset_uri(new_id),
        asset_origin="project_upload",
        reason="replace project photo",
    )
    result = StudioCommandExecutor().execute(scene, command, _context(scene))
    assert result.success is True
    node = result.candidate_scene.node_by_id("photo_1") if result.candidate_scene else None
    assert isinstance(node, ImageNode)
    assert node.asset_id == new_id
    assert node.storage_uri == project_asset_uri(new_id)
    assert node.asset_origin == "project_upload"
    assert result.candidate_scene is not None
    assert any(ref.asset_id == new_id for ref in result.candidate_scene.asset_manifest)
    action = result.applied_actions[0]
    assert action.command_id == command.command_id
    assert action.after_payload["asset_origin"] == "project_upload"
    assert action.after_payload["asset_id"] == str(new_id)


def test_replace_asset_rejects_drawing_node() -> None:
    scene = _render_scene(_drawing_node(node_id="plan"))
    command = ReplaceAssetCommand(
        presentation_id=uuid4(),
        slide_id=scene.slide_id,
        node_id="plan",
        asset_id=uuid4(),
        storage_uri="project://plan.png",
    )
    result = StudioCommandExecutor().execute(scene, command, _context(scene))
    assert result.success is False
    assert any(issue.code == "STUDIO.NODE_NOT_IMAGE" for issue in result.issues)


def test_replace_asset_rejects_reference_template_origin() -> None:
    scene = _render_scene(_image_node(node_id="photo_1"))
    command = ReplaceAssetCommand(
        presentation_id=uuid4(),
        slide_id=scene.slide_id,
        node_id="photo_1",
        asset_id=uuid4(),
        storage_uri="reference://template/photo.png",
        asset_origin="reference_case",
    )
    context = StudioExecutionContext(
        presentation_id=uuid4(),
        forbidden_asset_origins=frozenset({"reference_template", "reference_case"}),
    )
    result = StudioCommandExecutor().execute(scene, command, context)
    assert result.success is False
    assert any(issue.code == "STUDIO.FORBIDDEN_ASSET_ORIGIN" for issue in result.issues)


def test_replace_asset_rejects_locked_node() -> None:
    scene = _render_scene(_image_node(node_id="photo_1", locked=True))
    command = ReplaceAssetCommand(
        presentation_id=uuid4(),
        slide_id=scene.slide_id,
        node_id="photo_1",
        asset_id=uuid4(),
        storage_uri="project://new.png",
    )
    result = StudioCommandExecutor().execute(scene, command, _context(scene))
    assert result.success is False
    assert node_asset_locked(scene.node_by_id("photo_1"))  # type: ignore[arg-type]


def test_replace_drawing_updates_node_and_keeps_contain() -> None:
    new_id = uuid4()
    scene = _render_scene(_drawing_node(node_id="site_plan"))
    command = ReplaceDrawingCommand(
        presentation_id=uuid4(),
        slide_id=scene.slide_id,
        node_id="site_plan",
        asset_id=new_id,
        storage_uri=project_asset_uri(new_id),
        drawing_type="site_plan",
        reason="replace site plan",
    )
    result = StudioCommandExecutor().execute(scene, command, _context(scene))
    assert result.success is True
    node = result.candidate_scene.node_by_id("site_plan") if result.candidate_scene else None
    assert isinstance(node, DrawingNode)
    assert node.asset_id == new_id
    assert node.fit_mode == "contain"
    assert node.storage_uri == project_asset_uri(new_id)
    action = result.applied_actions[0]
    assert action.after_payload["drawing_type"] == "site_plan"
    assert action.after_payload["preserve_aspect_ratio"] is True
    assert action.after_payload["preserve_annotations"] is True


def test_replace_drawing_rejects_image_node() -> None:
    scene = _render_scene(_image_node(node_id="photo"))
    command = ReplaceDrawingCommand(
        presentation_id=uuid4(),
        slide_id=scene.slide_id,
        node_id="photo",
        asset_id=uuid4(),
        storage_uri="project://plan.png",
    )
    result = StudioCommandExecutor().execute(scene, command, _context(scene))
    assert result.success is False
    assert any(issue.code == "STUDIO.NODE_NOT_DRAWING" for issue in result.issues)


def test_increase_drawing_readability_enlarges_drawing() -> None:
    from archium.application.visual.drawing_readability_service import node_area_ratio
    from archium.domain.visual.studio_command import IncreaseDrawingReadabilityCommand

    scene = RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=10,
        page_height=5.625,
        background=BackgroundStyle(color="#FFFFFF"),
        nodes=[
            TextNode(
                id="title",
                semantic_role="title",
                x=0.8,
                y=0.3,
                width=8.4,
                height=0.5,
                z_index=2,
                text="院区总平面",
                font_family="Arial",
                font_size=20,
                color="#000000",
                line_height=1.2,
            ),
            _drawing_node(node_id="site_plan", storage_uri="project://plan.png"),
            _text_node(
                node_id="body",
                text="说明文字覆盖在图面上方用于测试压缩与重排。" * 3,
                x=1.0,
                y=1.2,
                width=4.0,
                height=1.0,
            ),
        ],
    )
    drawing = scene.node_by_id("site_plan")
    assert isinstance(drawing, DrawingNode)
    drawing.width = 3.0
    drawing.height = 2.0
    before_ratio = node_area_ratio(drawing, scene)

    command = IncreaseDrawingReadabilityCommand(
        presentation_id=uuid4(),
        slide_id=scene.slide_id,
        node_id="site_plan",
        target_min_area_ratio=0.45,
    )
    result = StudioCommandExecutor().execute(scene, command, _context(scene))
    assert result.success is True
    assert result.candidate_scene is not None
    updated = result.candidate_scene.node_by_id("site_plan")
    assert isinstance(updated, DrawingNode)
    assert updated.fit_mode == "contain"
    assert node_area_ratio(updated, result.candidate_scene) > before_ratio
    assert any(action.action_type == "enlarge_drawing" for action in result.applied_actions)


def test_increase_drawing_readability_rejects_locked_geometry() -> None:
    from archium.domain.visual.studio_command import IncreaseDrawingReadabilityCommand

    scene = _render_scene(
        _drawing_node(node_id="site_plan", locked=True),
    )
    command = IncreaseDrawingReadabilityCommand(
        presentation_id=uuid4(),
        slide_id=scene.slide_id,
        node_id="site_plan",
    )
    result = StudioCommandExecutor().execute(scene, command, _context(scene))
    assert result.success is False
    assert any("locked" in item for item in result.skipped_actions)


def test_replace_asset_rejects_invalid_project_uri() -> None:
    new_id = uuid4()
    scene = _render_scene(_image_node(node_id="photo_1"))
    command = ReplaceAssetCommand(
        presentation_id=uuid4(),
        slide_id=scene.slide_id,
        node_id="photo_1",
        asset_id=new_id,
        storage_uri="project://site/photo-02.png",
    )
    result = StudioCommandExecutor().execute(
        scene,
        command,
        _context(scene, validate_asset_bindings=True),
    )
    assert result.success is False
    assert any(issue.code == "STUDIO.ASSET_URI_UNSUPPORTED" for issue in result.issues)


def test_replace_asset_rejects_uri_asset_id_mismatch() -> None:
    new_id = uuid4()
    other_id = uuid4()
    scene = _render_scene(_image_node(node_id="photo_1"))
    command = ReplaceAssetCommand(
        presentation_id=uuid4(),
        slide_id=scene.slide_id,
        node_id="photo_1",
        asset_id=new_id,
        storage_uri=project_asset_uri(other_id),
    )
    result = StudioCommandExecutor().execute(
        scene,
        command,
        _context(scene, validate_asset_bindings=True),
    )
    assert result.success is False
    assert any(issue.code == "STUDIO.ASSET_URI_MISMATCH" for issue in result.issues)


def test_replace_asset_accepts_resolvable_benchmark_uri(tmp_path) -> None:  # noqa: ANN001
    from PIL import Image

    new_id = uuid4()
    case_dir = tmp_path / "case_photo"
    assets = case_dir / "assets"
    assets.mkdir(parents=True)
    asset_file = assets / f"{new_id}.png"
    Image.new("RGB", (1, 1), color="red").save(asset_file)
    uri = benchmark_asset_uri("case_photo", f"assets/{new_id}.png")
    scene = _render_scene(_image_node(node_id="photo_1"))
    command = ReplaceAssetCommand(
        presentation_id=uuid4(),
        slide_id=scene.slide_id,
        node_id="photo_1",
        asset_id=new_id,
        storage_uri=uri,
    )
    result = StudioCommandExecutor().execute(
        scene,
        command,
        _context(
            scene,
            validate_asset_bindings=True,
            asset_resolve_context=AssetPathResolveContext(
                case_dir=case_dir,
                case_id="case_photo",
                assets_dir=assets,
                benchmark_root=tmp_path,
            ),
        ),
    )
    assert result.success is True

