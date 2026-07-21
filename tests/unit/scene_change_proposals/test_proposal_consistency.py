"""Consistency tests for Studio Proposal / Patch Replay / Repair boundaries.

These cover the audit-critical invariants from the P0/P1 hardening backlog:
1. Patch Replay equivalence (command execute == patch replay)
2. Partial-accept audit (commands, status, untouched nodes)
3. Asset manifest consistency after replace
4. Stale proposal rejection
5. RewriteText multi-paragraph cleanup
6. Deterministic vs semantic repair boundaries
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from archium.application.visual.asset_path_resolver import project_asset_uri
from archium.application.visual.scene_proposal_service import (
    SceneProposalService,
    apply_patch_actions,
    resolve_accepted_commands,
)
from archium.application.visual.scene_repair_service import SceneRepairService
from archium.application.visual.studio_command_executor import (
    StudioCommandExecutor,
    StudioExecutionContext,
)
from archium.domain.slide_semantic_qa import SlideSemanticFinding
from archium.domain.visual.render_scene import (
    BackgroundStyle,
    DrawingNode,
    ImageNode,
    RenderScene,
    SceneAssetReference,
    TextNode,
    compute_scene_hash,
)
from archium.domain.visual.scene_change_proposal import ProposalDecision, ProposalStatus
from archium.domain.visual.scene_qa import SceneSemanticCheckCode
from archium.domain.visual.scene_repair import SceneRepairApplyMode
from archium.domain.visual.studio_command import (
    FixOverflowCommand,
    IncreaseDrawingReadabilityCommand,
    ReplaceAssetCommand,
    ReplaceDrawingCommand,
    RewriteTextCommand,
)
from archium.exceptions import WorkflowError


def _text_node(
    *,
    node_id: str,
    text: str,
    width: float = 2.0,
    height: float = 0.4,
    overflow: str = "error",
    locked: bool = False,
) -> TextNode:
    return TextNode(
        id=node_id,
        x=0.5,
        y=1.0,
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
    )


def _image_node(*, node_id: str, asset_id, asset_origin: str = "project_upload") -> ImageNode:
    uri = project_asset_uri(asset_id)
    return ImageNode(
        id=node_id,
        x=1.0,
        y=1.0,
        width=3.0,
        height=2.0,
        z_index=1,
        storage_uri=uri,
        asset_path=uri,
        asset_id=asset_id,
        asset_origin=asset_origin,  # type: ignore[arg-type]
    )


def _drawing_node(*, node_id: str, asset_id, width: float = 3.0, height: float = 2.0) -> DrawingNode:
    uri = project_asset_uri(asset_id)
    return DrawingNode(
        id=node_id,
        x=2.0,
        y=1.0,
        width=width,
        height=height,
        z_index=1,
        storage_uri=uri,
        asset_path=uri,
        asset_id=asset_id,
        fit_mode="contain",
        drawing_type="site_plan",
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


def _executor() -> StudioCommandExecutor:
    return StudioCommandExecutor()


def _proposal_service() -> SceneProposalService:
    service = SceneProposalService.__new__(SceneProposalService)
    service._executor = _executor()
    service._scenes = None  # type: ignore[assignment]
    service._proposals = None  # type: ignore[assignment]
    service._presentations = None  # type: ignore[assignment]
    service._scene_history = None  # type: ignore[assignment]
    service._studio_scene = None  # type: ignore[assignment]
    service._settings = None  # type: ignore[assignment]
    service._session = None  # type: ignore[assignment]
    return service


def _assert_patch_equivalence(base: RenderScene, command, *, context: StudioExecutionContext | None = None) -> None:
    ctx = context or StudioExecutionContext(presentation_id=command.presentation_id)
    result = _executor().execute(base, command, ctx)
    assert result.success
    assert result.candidate_scene is not None
    assert result.applied_actions, f"expected patches for {command.command_type}"
    replayed = apply_patch_actions(base, list(result.applied_actions))
    assert compute_scene_hash(result.candidate_scene) == compute_scene_hash(replayed)


# ---------------------------------------------------------------------------
# 1. Patch Replay equivalence
# ---------------------------------------------------------------------------


def test_patch_equivalence_rewrite_text() -> None:
    scene = _scene(_text_node(node_id="title", text="旧标题"))
    scene.nodes[0].paragraphs = [
        {"text": "旧标题", "alignment": "left"},
        {"text": "旧段落二", "alignment": "left"},
    ]
    command = RewriteTextCommand(
        presentation_id=uuid4(),
        slide_id=scene.slide_id,
        node_id="title",
        new_text="结论：交通组织优化",
    )
    _assert_patch_equivalence(scene, command)


def test_patch_equivalence_replace_asset() -> None:
    old_id = uuid4()
    new_id = uuid4()
    scene = _scene(_image_node(node_id="photo_1", asset_id=old_id))
    scene.asset_manifest = [
        SceneAssetReference(
            asset_id=old_id,
            storage_uri=project_asset_uri(old_id),
            asset_path=project_asset_uri(old_id),
            origin="project_upload",
        )
    ]
    command = ReplaceAssetCommand(
        presentation_id=uuid4(),
        slide_id=scene.slide_id,
        node_id="photo_1",
        asset_id=new_id,
        storage_uri=project_asset_uri(new_id),
        asset_origin="reference_case",
    )
    _assert_patch_equivalence(scene, command)


def test_patch_equivalence_replace_drawing() -> None:
    old_id = uuid4()
    new_id = uuid4()
    scene = _scene(_drawing_node(node_id="site_plan", asset_id=old_id))
    command = ReplaceDrawingCommand(
        presentation_id=uuid4(),
        slide_id=scene.slide_id,
        node_id="site_plan",
        asset_id=new_id,
        storage_uri=project_asset_uri(new_id),
        drawing_type="elevation",
    )
    _assert_patch_equivalence(scene, command)


def test_patch_equivalence_fix_overflow() -> None:
    long_text = "这是一段非常长的说明文字，用于验证溢出修复。" * 20
    scene = _scene(_text_node(node_id="body", text=long_text, width=1.5, height=0.3))
    presentation_id = uuid4()
    command = FixOverflowCommand(
        presentation_id=presentation_id,
        slide_id=scene.slide_id,
    )
    _assert_patch_equivalence(
        scene,
        command,
        context=StudioExecutionContext(presentation_id=presentation_id),
    )


def test_patch_equivalence_increase_drawing_readability() -> None:
    scene = _scene(
        _drawing_node(node_id="site_plan", asset_id=uuid4(), width=3.0, height=2.0),
        _text_node(node_id="body", text="支撑说明" * 30, width=3.0, height=1.0),
    )
    command = IncreaseDrawingReadabilityCommand(
        presentation_id=uuid4(),
        slide_id=scene.slide_id,
        node_id="site_plan",
        target_min_area_ratio=0.45,
    )
    _assert_patch_equivalence(scene, command)


# ---------------------------------------------------------------------------
# 2. Partial-accept audit
# ---------------------------------------------------------------------------


def test_partial_accept_audit_records_only_related_command() -> None:
    scene = _scene(
        _text_node(node_id="title", text="旧标题"),
        _text_node(node_id="body", text="旧正文", width=3.0, height=0.5),
    )
    presentation_id = uuid4()
    service = _proposal_service()
    title_cmd = RewriteTextCommand(
        presentation_id=presentation_id,
        slide_id=scene.slide_id,
        node_id="title",
        new_text="新标题",
    )
    body_cmd = RewriteTextCommand(
        presentation_id=presentation_id,
        slide_id=scene.slide_id,
        node_id="body",
        new_text="新正文",
    )
    proposal = service.create_proposal(
        base_scene=scene,
        commands=[title_cmd, body_cmd],
        presentation_id=presentation_id,
        slide_id=scene.slide_id,
    )
    title_action = next(a for a in proposal.patch_actions if a.node_id == "title")
    decision = ProposalDecision(
        proposal_id=proposal.proposal_id,
        accepted_action_ids=[title_action.action_id],
    )

    accepted_scene = service._resolve_accepted_scene(proposal, decision)
    accepted_commands = resolve_accepted_commands(proposal, decision)

    assert accepted_scene.node_by_id("title").text == "新标题"  # type: ignore[union-attr]
    assert accepted_scene.node_by_id("body").text == "旧正文"  # type: ignore[union-attr]
    assert len(accepted_commands) == 1
    assert accepted_commands[0].command_id == title_cmd.command_id
    assert body_cmd.command_id not in {c.command_id for c in accepted_commands}

    class _Repo:
        saved = None

        def save(self, proposal, *, supersede_previous: bool = True):
            self.saved = proposal
            return proposal

    service._proposals = _Repo()  # type: ignore[assignment]
    updated = service._record_proposal_decision(proposal, decision)
    assert updated.status == ProposalStatus.PARTIALLY_ACCEPTED
    assert updated.decision is not None
    assert updated.decision.accepted_action_ids == [title_action.action_id]
    assert title_action.action_id not in set(updated.decision.rejected_action_ids)


# ---------------------------------------------------------------------------
# 3. Asset manifest consistency
# ---------------------------------------------------------------------------


def test_replace_asset_keeps_node_and_manifest_consistent() -> None:
    old_id = uuid4()
    new_id = uuid4()
    scene = _scene(_image_node(node_id="photo_1", asset_id=old_id))
    scene.asset_manifest = [
        SceneAssetReference(
            asset_id=old_id,
            storage_uri=project_asset_uri(old_id),
            asset_path=project_asset_uri(old_id),
            origin="project_upload",
        )
    ]
    command = ReplaceAssetCommand(
        presentation_id=uuid4(),
        slide_id=scene.slide_id,
        node_id="photo_1",
        asset_id=new_id,
        storage_uri=project_asset_uri(new_id),
        asset_origin="reference_case",
    )
    result = _executor().execute(
        scene,
        command,
        StudioExecutionContext(presentation_id=command.presentation_id),
    )
    assert result.success and result.candidate_scene is not None
    photo = result.candidate_scene.node_by_id("photo_1")
    assert isinstance(photo, ImageNode)
    assert photo.asset_id == new_id
    assert photo.storage_uri == project_asset_uri(new_id)
    assert photo.asset_origin == "reference_case"
    matching = [
        ref for ref in result.candidate_scene.asset_manifest if ref.asset_id == new_id
    ]
    assert len(matching) == 1
    assert matching[0].storage_uri == project_asset_uri(new_id)
    assert matching[0].origin == "reference_case"

    replayed = apply_patch_actions(scene, list(result.applied_actions))
    replayed_photo = replayed.node_by_id("photo_1")
    assert isinstance(replayed_photo, ImageNode)
    assert replayed_photo.asset_id == new_id
    assert replayed_photo.storage_uri == project_asset_uri(new_id)
    assert replayed_photo.asset_origin == "reference_case"
    assert any(ref.asset_id == new_id for ref in replayed.asset_manifest)


# ---------------------------------------------------------------------------
# 4. Stale proposal
# ---------------------------------------------------------------------------


def test_stale_proposal_is_superseded_and_cannot_accept() -> None:
    scene = _scene(_text_node(node_id="title", text="旧标题"))
    presentation_id = uuid4()
    service = _proposal_service()
    proposal = service.create_proposal(
        base_scene=scene,
        commands=[
            RewriteTextCommand(
                presentation_id=presentation_id,
                slide_id=scene.slide_id,
                node_id="title",
                new_text="新标题",
            )
        ],
        presentation_id=presentation_id,
        slide_id=scene.slide_id,
    )
    current = scene.model_copy(deep=True)
    title = current.node_by_id("title")
    assert isinstance(title, TextNode)
    title.text = "页面已被人工改过"
    assert service.is_stale(proposal, current)

    class _Repo:
        saved = None

        def save(self, proposal, *, supersede_previous: bool = True):
            self.saved = proposal
            return proposal

    service._proposals = _Repo()  # type: ignore[assignment]
    service._scenes = type("S", (), {"get_by_layout_plan": staticmethod(lambda *_: current)})()  # type: ignore[assignment]

    from archium.domain.slide import SlideSpec
    from archium.domain.enums import SlideType

    slide = SlideSpec(
        id=scene.slide_id,
        presentation_id=presentation_id,
        title="T",
        slide_type=SlideType.CONTENT,
        order=0,
        chapter_id="ch1",
        message="stale test",
        layout_plan_id=scene.layout_plan_id,
    )
    with pytest.raises(WorkflowError, match="重新生成"):
        service.accept_proposal(proposal, slide, current_scene=current)
    assert service._proposals.saved is not None  # type: ignore[attr-defined]
    assert service._proposals.saved.status == ProposalStatus.SUPERSEDED  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# 5. RewriteText multi-paragraph
# ---------------------------------------------------------------------------


def test_rewrite_text_collapses_all_paragraphs_consistently() -> None:
    scene = _scene(_text_node(node_id="body", text="旧段落一"))
    body = scene.node_by_id("body")
    assert isinstance(body, TextNode)
    body.paragraphs = [
        {"text": "旧段落一", "alignment": "left"},
        {"text": "旧段落二", "alignment": "left"},
        {"text": "旧段落三", "alignment": "center"},
    ]
    command = RewriteTextCommand(
        presentation_id=uuid4(),
        slide_id=scene.slide_id,
        node_id="body",
        new_text="合并后的新正文",
    )
    result = _executor().execute(
        scene,
        command,
        StudioExecutionContext(presentation_id=command.presentation_id),
    )
    assert result.candidate_scene is not None
    node = result.candidate_scene.node_by_id("body")
    assert isinstance(node, TextNode)
    assert node.text == "合并后的新正文"
    assert len(node.paragraphs) == 1
    assert node.paragraphs[0].text == "合并后的新正文"

    replayed = apply_patch_actions(scene, list(result.applied_actions))
    replayed_node = replayed.node_by_id("body")
    assert isinstance(replayed_node, TextNode)
    assert replayed_node.text == "合并后的新正文"
    assert len(replayed_node.paragraphs) == 1
    assert replayed_node.paragraphs[0].text == "合并后的新正文"
    assert compute_scene_hash(result.candidate_scene) == compute_scene_hash(replayed)


# ---------------------------------------------------------------------------
# 6. Auto-repair boundary
# ---------------------------------------------------------------------------


def test_deterministic_repair_auto_applies_cover_to_contain() -> None:
    scene = _scene(
        DrawingNode.model_construct(
            id="plan",
            x=1.0,
            y=1.0,
            width=4.0,
            height=3.0,
            z_index=1,
            storage_uri="project://drawing.png",
            asset_path="project://drawing.png",
            fit_mode="cover",
        )
    )
    finding = SlideSemanticFinding(
        check_code=SceneSemanticCheckCode.DRAWING_COVER_MODE_FORBIDDEN,
        slide_order=0,
        slide_id=scene.slide_id,
        severity="medium",
        title="cover forbidden",
        description="cover forbidden",
        evidence_refs=["plan"],
    )
    result = SceneRepairService().repair_scene(
        scene,
        [finding],
        apply_mode=SceneRepairApplyMode.SAFE_AUTO_ONLY,
    )
    drawing = result.scene.node_by_id("plan")
    assert isinstance(drawing, DrawingNode)
    assert drawing.fit_mode == "contain"
    assert result.applied_count == 1


def test_semantic_overflow_requires_proposal_mode() -> None:
    long_text = "这是一段非常长的说明文字" * 20
    scene = _scene(_text_node(node_id="body", text=long_text, width=1.5, height=0.3))
    finding = SlideSemanticFinding(
        check_code=SceneSemanticCheckCode.TEXT_OVERFLOW,
        slide_order=0,
        slide_id=scene.slide_id,
        severity="medium",
        title="overflow",
        description="overflow",
        evidence_refs=["body"],
    )

    safe = SceneRepairService().repair_scene(
        scene,
        [finding],
        apply_mode=SceneRepairApplyMode.SAFE_AUTO_ONLY,
    )
    assert safe.applied_count == 0
    assert safe.scene.node_by_id("body").text == long_text  # type: ignore[union-attr]

    proposal_mode = SceneRepairService().repair_scene(
        scene,
        [finding],
        apply_mode=SceneRepairApplyMode.ALL_REPAIRABLE,
    )
    assert proposal_mode.applied_count >= 1
    assert len(proposal_mode.scene.node_by_id("body").text) < len(long_text)  # type: ignore[union-attr]

    batch = SceneRepairService().repair_deck(
        uuid4(),
        [scene],
        max_rounds=1,
        slide_orders={scene.slide_id: 0},
        apply_mode=SceneRepairApplyMode.SAFE_AUTO_ONLY,
    )
    assert batch.deferred_findings
    assert batch.deferred_findings[0].check_code == SceneSemanticCheckCode.TEXT_OVERFLOW
