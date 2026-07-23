"""Unit tests for SceneChangeProposal workflow."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from archium.application.visual.asset_path_resolver import project_asset_uri
from archium.application.visual.scene_proposal_qa import compare_proposal_qa
from archium.application.visual.scene_proposal_service import (
    SceneProposalService,
    apply_patch_actions,
    resolve_accepted_commands,
)
from archium.domain.visual.page_quality import IssueSeverity, QualityIssue, QualityIssueSource
from archium.domain.visual.render_scene import (
    BackgroundStyle,
    DrawingNode,
    ImageNode,
    RenderScene,
    SceneAssetReference,
    TextNode,
    compute_scene_hash,
)
from archium.domain.visual.scene_change_proposal import ProposalStatus, SceneChangeProposal
from archium.domain.visual.scene_qa import SceneSemanticCheckCode
from archium.domain.visual.studio_command import (
    IncreaseDrawingReadabilityCommand,
    ReplaceAssetCommand,
    ReplaceDrawingCommand,
    RewriteTextCommand,
    build_patch_action,
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


def _scene(*nodes: TextNode) -> RenderScene:
    return RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=10,
        page_height=5.625,
        background=BackgroundStyle(color="#FFFFFF"),
        nodes=list(nodes),
    )


def test_create_proposal_runs_commands_and_qa() -> None:
    scene = _scene(_text_node(node_id="title", text="旧标题"))
    presentation_id = uuid4()
    service = SceneProposalService.__new__(SceneProposalService)
    service._executor = __import__(
        "archium.application.visual.studio_command_executor",
        fromlist=["StudioCommandExecutor"],
    ).StudioCommandExecutor()
    service._scenes = None  # type: ignore[assignment]
    service._presentations = None  # type: ignore[assignment]
    service._scene_history = None  # type: ignore[assignment]
    service._studio_scene = None  # type: ignore[assignment]
    service._settings = None  # type: ignore[assignment]
    service._session = None  # type: ignore[assignment]

    proposal = service.create_proposal(
        base_scene=scene,
        commands=[
            RewriteTextCommand(
                presentation_id=presentation_id,
                slide_id=scene.slide_id,
                node_id="title",
                new_text="结论：交通组织优化",
            )
        ],
        presentation_id=presentation_id,
        slide_id=scene.slide_id,
    )
    assert proposal.status == ProposalStatus.READY
    assert proposal.proposed_scene.node_by_id("title").text == "结论：交通组织优化"  # type: ignore[union-attr]
    assert proposal.patch_actions
    assert proposal.base_scene_hash != proposal.proposed_scene.scene_hash_input()


def test_create_proposal_fixes_overflow_qa() -> None:
    long_text = "这是一段非常长的说明文字，用于验证溢出修复。" * 15
    scene = _scene(_text_node(node_id="body", text=long_text, width=1.5, height=0.3))
    presentation_id = uuid4()
    service = SceneProposalService.__new__(SceneProposalService)
    service._executor = __import__(
        "archium.application.visual.studio_command_executor",
        fromlist=["StudioCommandExecutor"],
    ).StudioCommandExecutor()
    service._scenes = None  # type: ignore[assignment]
    service._presentations = None  # type: ignore[assignment]
    service._scene_history = None  # type: ignore[assignment]
    service._studio_scene = None  # type: ignore[assignment]
    service._settings = None  # type: ignore[assignment]
    service._session = None  # type: ignore[assignment]

    from archium.domain.visual.studio_command import FixOverflowCommand

    proposal = service.create_proposal(
        base_scene=scene,
        commands=[
            FixOverflowCommand(
                presentation_id=presentation_id,
                slide_id=scene.slide_id,
            )
        ],
        presentation_id=presentation_id,
        slide_id=scene.slide_id,
    )
    before_overflow = [
        issue for issue in proposal.qa_before if issue.code == SceneSemanticCheckCode.TEXT_OVERFLOW
    ]
    after_overflow = [
        issue for issue in proposal.qa_after if issue.code == SceneSemanticCheckCode.TEXT_OVERFLOW
    ]
    assert before_overflow
    assert not after_overflow


def test_compare_proposal_qa_resolved_and_introduced() -> None:
    before = [
        QualityIssue(
            code="SEMANTIC.TEXT_OVERFLOW",
            severity=IssueSeverity.BLOCKER,
            message="overflow",
            source=QualityIssueSource.AUTO,
            evidence=["body"],
        )
    ]
    after = [
        QualityIssue(
            code="SEMANTIC.FONT_TOO_SMALL",
            severity=IssueSeverity.MAJOR,
            message="small",
            source=QualityIssueSource.AUTO,
            evidence=["caption"],
        )
    ]
    diff = compare_proposal_qa(before, after)
    assert len(diff.resolved) == 1
    assert len(diff.introduced) == 1
    assert not diff.remaining


def test_apply_patch_actions_rewrite_text() -> None:
    scene = _scene(_text_node(node_id="title", text="旧"))
    scene.nodes[0].paragraphs = [
        {"text": "旧", "alignment": "left"},
        {"text": "旧段落二", "alignment": "left"},
    ]

    patched = apply_patch_actions(
        scene,
        [
            build_patch_action(
                scene,
                base_scene_hash=compute_scene_hash(scene),
                node_id="title",
                action_type="rewrite_text",
                after_value="新",
            )
        ],
    )
    node = patched.node_by_id("title")
    assert isinstance(node, TextNode)
    assert node.text == "新"
    assert len(node.paragraphs) == 1
    assert node.paragraphs[0].text == "新"


def test_resolve_accepted_scene_applies_subset() -> None:
    scene = _scene(
        _text_node(node_id="title", text="旧标题"),
        _text_node(node_id="body", text="旧正文", width=3.0, height=0.5),
    )
    presentation_id = uuid4()
    service = SceneProposalService.__new__(SceneProposalService)
    service._executor = __import__(
        "archium.application.visual.studio_command_executor",
        fromlist=["StudioCommandExecutor"],
    ).StudioCommandExecutor()
    service._scenes = None  # type: ignore[assignment]
    service._presentations = None  # type: ignore[assignment]
    service._scene_history = None  # type: ignore[assignment]
    service._studio_scene = None  # type: ignore[assignment]
    service._settings = None  # type: ignore[assignment]
    service._session = None  # type: ignore[assignment]

    proposal = service.create_proposal(
        base_scene=scene,
        commands=[
            RewriteTextCommand(
                presentation_id=presentation_id,
                slide_id=scene.slide_id,
                node_id="title",
                new_text="新标题",
            ),
            RewriteTextCommand(
                presentation_id=presentation_id,
                slide_id=scene.slide_id,
                node_id="body",
                new_text="新正文",
            ),
        ],
        presentation_id=presentation_id,
        slide_id=scene.slide_id,
    )
    from archium.domain.visual.scene_change_proposal import ProposalDecision

    title_action = next(
        action for action in proposal.patch_actions if action.node_id == "title"
    )
    accepted = service._resolve_accepted_scene(
        proposal,
        ProposalDecision(
            proposal_id=proposal.proposal_id,
            accepted_action_ids=[title_action.action_id],
        ),
    )
    assert accepted.node_by_id("title").text == "新标题"  # type: ignore[union-attr]
    assert accepted.node_by_id("body").text == "旧正文"  # type: ignore[union-attr]


def test_create_proposal_requires_commands() -> None:
    scene = _scene(_text_node(node_id="title", text="x"))
    service = SceneProposalService.__new__(SceneProposalService)
    service._executor = None  # type: ignore[assignment]
    try:
        service.create_proposal(
            base_scene=scene,
            commands=[],
            presentation_id=uuid4(),
            slide_id=scene.slide_id,
        )
        raised = False
    except WorkflowError:
        raised = True
    assert raised


def _image_node(
    *,
    node_id: str,
    asset_id: UUID | None = None,
    storage_uri: str = "project://old-photo.png",
    asset_origin: str = "project_upload",
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
        asset_origin=asset_origin,  # type: ignore[arg-type]
    )


def _drawing_node(
    *,
    node_id: str,
    asset_id: UUID | None = None,
    storage_uri: str = "project://old-plan.png",
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
    )


def _mixed_scene(*nodes) -> RenderScene:
    return RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=10,
        page_height=5.625,
        background=BackgroundStyle(color="#FFFFFF"),
        nodes=list(nodes),
    )


def _proposal_service() -> SceneProposalService:
    service = SceneProposalService.__new__(SceneProposalService)
    executor_module = __import__(
        "archium.application.visual.studio_command_executor",
        fromlist=["StudioCommandExecutor", "StudioExecutionContext"],
    )
    service._executor = executor_module.StudioCommandExecutor()
    service._executor._asset_validator = __import__(
        "archium.application.visual.asset_binding_validator",
        fromlist=["AssetBindingValidator"],
    ).AssetBindingValidator()
    service._scenes = None  # type: ignore[assignment]
    service._presentations = None  # type: ignore[assignment]
    service._scene_history = None  # type: ignore[assignment]
    service._studio_scene = None  # type: ignore[assignment]
    service._settings = None  # type: ignore[assignment]
    service._session = None  # type: ignore[assignment]
    return service


def test_partial_accept_replace_asset_preserves_manifest_and_origin() -> None:
    old_id = uuid4()
    new_id = uuid4()
    scene = _mixed_scene(
        _text_node(node_id="title", text="旧标题"),
        _image_node(node_id="photo_1", asset_id=old_id, asset_origin="project_upload"),
    )
    scene.asset_manifest = [
        SceneAssetReference(
            asset_id=old_id,
            storage_uri="project://old-photo.png",
            asset_path="project://old-photo.png",
            origin="project_upload",
        )
    ]
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
            ),
            ReplaceAssetCommand(
                presentation_id=presentation_id,
                slide_id=scene.slide_id,
                node_id="photo_1",
                asset_id=new_id,
                storage_uri=project_asset_uri(new_id),
                asset_origin="reference_case",
                reason="replace project photo",
            ),
        ],
        presentation_id=presentation_id,
        slide_id=scene.slide_id,
    )
    from archium.domain.visual.scene_change_proposal import ProposalDecision

    asset_action = next(
        action for action in proposal.patch_actions if action.action_type == "replace_asset"
    )
    accepted = service._resolve_accepted_scene(
        proposal,
        ProposalDecision(
            proposal_id=proposal.proposal_id,
            accepted_action_ids=[asset_action.action_id],
        ),
    )
    photo = accepted.node_by_id("photo_1")
    assert isinstance(photo, ImageNode)
    assert photo.asset_id == new_id
    assert photo.storage_uri == project_asset_uri(new_id)
    assert photo.asset_origin == "reference_case"
    assert any(ref.asset_id == new_id for ref in accepted.asset_manifest)
    assert accepted.node_by_id("title").text == "旧标题"  # type: ignore[union-attr]


def test_partial_accept_replace_drawing_preserves_drawing_metadata() -> None:
    old_id = uuid4()
    new_id = uuid4()
    scene = _mixed_scene(_drawing_node(node_id="site_plan", asset_id=old_id))
    presentation_id = uuid4()
    service = _proposal_service()

    proposal = service.create_proposal(
        base_scene=scene,
        commands=[
            ReplaceDrawingCommand(
                presentation_id=presentation_id,
                slide_id=scene.slide_id,
                node_id="site_plan",
                asset_id=new_id,
                storage_uri=project_asset_uri(new_id),
                drawing_type="elevation",
                preserve_aspect_ratio=True,
                preserve_annotations=True,
            )
        ],
        presentation_id=presentation_id,
        slide_id=scene.slide_id,
    )
    from archium.domain.visual.scene_change_proposal import ProposalDecision

    drawing_action = proposal.patch_actions[0]
    accepted = service._resolve_accepted_scene(
        proposal,
        ProposalDecision(
            proposal_id=proposal.proposal_id,
            accepted_action_ids=[drawing_action.action_id],
        ),
    )
    drawing = accepted.node_by_id("site_plan")
    assert isinstance(drawing, DrawingNode)
    assert drawing.asset_id == new_id
    assert drawing.drawing_type == "elevation"
    assert drawing.fit_mode == "contain"
    assert drawing.preserve_aspect_ratio is True
    assert drawing.preserve_annotations is True
    assert any(ref.asset_id == new_id for ref in accepted.asset_manifest)


def test_apply_patch_actions_replace_asset_uses_after_payload() -> None:
    old_id = uuid4()
    new_id = uuid4()
    scene = _mixed_scene(_image_node(node_id="photo_1", asset_id=old_id))
    scene.asset_manifest = [
        SceneAssetReference(
            asset_id=old_id,
            storage_uri="project://old-photo.png",
            asset_path="project://old-photo.png",
            origin="project_upload",
        )
    ]
    patched = apply_patch_actions(
        scene,
        [
            build_patch_action(
                scene,
                base_scene_hash=compute_scene_hash(scene),
                node_id="photo_1",
                action_type="replace_asset",
                after_value=project_asset_uri(new_id),
                after_asset_id=new_id,
                after_payload={
                    "asset_id": str(new_id),
                    "storage_uri": project_asset_uri(new_id),
                    "asset_origin": "reference_case",
                },
            )
        ],
    )
    photo = patched.node_by_id("photo_1")
    assert isinstance(photo, ImageNode)
    assert photo.asset_origin == "reference_case"
    assert any(ref.asset_id == new_id for ref in patched.asset_manifest)


def test_resolve_accepted_commands_returns_only_selected_commands() -> None:
    old_id = uuid4()
    new_id = uuid4()
    scene = _mixed_scene(
        _text_node(node_id="title", text="旧标题"),
        _image_node(node_id="photo_1", asset_id=old_id),
        _drawing_node(node_id="site_plan", asset_id=uuid4()),
    )
    scene.nodes[2].width = 3.0  # type: ignore[union-attr]
    scene.nodes[2].height = 2.0  # type: ignore[union-attr]
    presentation_id = uuid4()
    service = _proposal_service()

    rewrite_cmd = RewriteTextCommand(
        presentation_id=presentation_id,
        slide_id=scene.slide_id,
        node_id="title",
        new_text="新标题",
    )
    replace_cmd = ReplaceAssetCommand(
        presentation_id=presentation_id,
        slide_id=scene.slide_id,
        node_id="photo_1",
        asset_id=new_id,
        storage_uri=project_asset_uri(new_id),
    )
    enlarge_cmd = IncreaseDrawingReadabilityCommand(
        presentation_id=presentation_id,
        slide_id=scene.slide_id,
        node_id="site_plan",
        target_min_area_ratio=0.45,
    )
    proposal = service.create_proposal(
        base_scene=scene,
        commands=[rewrite_cmd, replace_cmd, enlarge_cmd],
        presentation_id=presentation_id,
        slide_id=scene.slide_id,
    )
    from archium.domain.visual.scene_change_proposal import ProposalDecision

    enlarge_actions = [
        action
        for action in proposal.patch_actions
        if action.command_id == enlarge_cmd.command_id
    ]
    assert enlarge_actions

    accepted_commands = resolve_accepted_commands(
        proposal,
        ProposalDecision(
            proposal_id=proposal.proposal_id,
            accepted_action_ids=[action.action_id for action in enlarge_actions],
        ),
    )
    assert len(accepted_commands) == 1
    assert accepted_commands[0].command_id == enlarge_cmd.command_id


def test_resolve_accepted_commands_returns_all_when_fully_accepted() -> None:
    scene = _scene(_text_node(node_id="title", text="旧"))
    presentation_id = uuid4()
    service = _proposal_service()
    proposal = service.create_proposal(
        base_scene=scene,
        commands=[
            RewriteTextCommand(
                presentation_id=presentation_id,
                slide_id=scene.slide_id,
                node_id="title",
                new_text="新",
            )
        ],
        presentation_id=presentation_id,
        slide_id=scene.slide_id,
    )
    from archium.domain.visual.scene_change_proposal import ProposalDecision

    accepted_commands = resolve_accepted_commands(
        proposal,
        ProposalDecision(
            proposal_id=proposal.proposal_id,
            accepted_action_ids=[action.action_id for action in proposal.patch_actions],
        ),
    )
    assert len(accepted_commands) == len(proposal.commands)


def test_resolve_accepted_commands_returns_all_when_no_decision() -> None:
    scene = _scene(_text_node(node_id="title", text="旧"))
    presentation_id = uuid4()
    service = _proposal_service()
    proposal = service.create_proposal(
        base_scene=scene,
        commands=[
            RewriteTextCommand(
                presentation_id=presentation_id,
                slide_id=scene.slide_id,
                node_id="title",
                new_text="新",
            )
        ],
        presentation_id=presentation_id,
        slide_id=scene.slide_id,
    )
    assert resolve_accepted_commands(proposal, None) == proposal.commands


def test_create_proposal_records_failed_commands_with_warnings() -> None:
    scene = _mixed_scene(
        _text_node(node_id="title", text="旧标题", locked=True),
        _text_node(node_id="body", text="旧正文"),
    )
    presentation_id = uuid4()
    service = _proposal_service()

    locked_rewrite = RewriteTextCommand(
        presentation_id=presentation_id,
        slide_id=scene.slide_id,
        node_id="title",
        new_text="新标题",
    )
    body_rewrite = RewriteTextCommand(
        presentation_id=presentation_id,
        slide_id=scene.slide_id,
        node_id="body",
        new_text="新正文",
    )
    proposal = service.create_proposal(
        base_scene=scene,
        commands=[locked_rewrite, body_rewrite],
        presentation_id=presentation_id,
        slide_id=scene.slide_id,
    )

    assert proposal.status == ProposalStatus.READY_WITH_WARNINGS
    assert len(proposal.requested_commands) == 2
    assert len(proposal.successful_commands) == 1
    assert len(proposal.failed_commands) == 1
    assert proposal.commands == proposal.successful_commands
    assert proposal.failed_commands[0].command_id == locked_rewrite.command_id
    assert proposal.proposed_scene.node_by_id("body").text == "新正文"  # type: ignore[union-attr]
    assert proposal.proposed_scene.node_by_id("title").text == "旧标题"  # type: ignore[union-attr]

    failed_result = next(
        result for result in proposal.command_results if result.status == "failed"
    )
    assert failed_result.command_id == locked_rewrite.command_id
    assert failed_result.issues
    assert failed_result.action_ids == []

    applied_result = next(
        result for result in proposal.command_results if result.status == "applied"
    )
    assert applied_result.command_id == body_rewrite.command_id
    assert applied_result.action_ids


def test_create_proposal_raises_when_all_commands_fail() -> None:
    scene = _scene(_text_node(node_id="title", text="旧标题", locked=True))
    presentation_id = uuid4()
    service = _proposal_service()
    try:
        service.create_proposal(
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
        raised = False
    except WorkflowError:
        raised = True
    assert raised


class _RecordingProposalRepository:
    def __init__(self) -> None:
        self.saved: SceneChangeProposal | None = None

    def save(
        self,
        proposal: SceneChangeProposal,
        *,
        supersede_previous: bool = True,
    ) -> SceneChangeProposal:
        self.saved = proposal
        return proposal


def _service_with_recording_repo() -> tuple[SceneProposalService, _RecordingProposalRepository]:
    service = SceneProposalService.__new__(SceneProposalService)
    repo = _RecordingProposalRepository()
    service._proposals = repo  # type: ignore[assignment]
    return service, repo


def test_record_proposal_decision_full_accept() -> None:
    scene = _scene(_text_node(node_id="title", text="旧"))
    presentation_id = uuid4()
    service, repo = _service_with_recording_repo()
    proposal = _proposal_service().create_proposal(
        base_scene=scene,
        commands=[
            RewriteTextCommand(
                presentation_id=presentation_id,
                slide_id=scene.slide_id,
                node_id="title",
                new_text="新",
            )
        ],
        presentation_id=presentation_id,
        slide_id=scene.slide_id,
    )

    updated = service._record_proposal_decision(proposal, None)

    assert updated.status == ProposalStatus.ACCEPTED
    assert updated.decision is not None
    assert updated.decision.accepted_action_ids == [
        action.action_id for action in proposal.patch_actions
    ]
    assert updated.decided_at is not None
    assert repo.saved is not None
    assert repo.saved.status == ProposalStatus.ACCEPTED


def test_record_proposal_decision_partial_accept() -> None:
    scene = _mixed_scene(
        _text_node(node_id="title", text="旧标题"),
        _text_node(node_id="body", text="旧正文"),
    )
    presentation_id = uuid4()
    service, repo = _service_with_recording_repo()
    proposal = _proposal_service().create_proposal(
        base_scene=scene,
        commands=[
            RewriteTextCommand(
                presentation_id=presentation_id,
                slide_id=scene.slide_id,
                node_id="title",
                new_text="新标题",
            ),
            RewriteTextCommand(
                presentation_id=presentation_id,
                slide_id=scene.slide_id,
                node_id="body",
                new_text="新正文",
            ),
        ],
        presentation_id=presentation_id,
        slide_id=scene.slide_id,
    )
    from archium.domain.visual.scene_change_proposal import ProposalDecision

    title_action = proposal.patch_actions[0]
    updated = service._record_proposal_decision(
        proposal,
        ProposalDecision(
            proposal_id=proposal.proposal_id,
            accepted_action_ids=[title_action.action_id],
        ),
    )

    assert updated.status == ProposalStatus.PARTIALLY_ACCEPTED
    assert updated.decision is not None
    assert updated.decision.accepted_action_ids == [title_action.action_id]
    assert repo.saved is not None
    assert repo.saved.status == ProposalStatus.PARTIALLY_ACCEPTED


def test_mark_proposal_superseded_persists_status() -> None:
    scene = _scene(_text_node(node_id="title", text="旧"))
    presentation_id = uuid4()
    service, repo = _service_with_recording_repo()
    proposal = _proposal_service().create_proposal(
        base_scene=scene,
        commands=[
            RewriteTextCommand(
                presentation_id=presentation_id,
                slide_id=scene.slide_id,
                node_id="title",
                new_text="新",
            )
        ],
        presentation_id=presentation_id,
        slide_id=scene.slide_id,
    )

    updated = service.mark_proposal_superseded(proposal)

    assert updated.status == ProposalStatus.SUPERSEDED
    assert updated.decided_at is not None
    assert repo.saved is not None
    assert repo.saved.status == ProposalStatus.SUPERSEDED


def test_reject_proposal_persists_decision() -> None:
    scene = _scene(_text_node(node_id="title", text="旧"))
    presentation_id = uuid4()
    service, repo = _service_with_recording_repo()
    proposal = _proposal_service().create_proposal(
        base_scene=scene,
        commands=[
            RewriteTextCommand(
                presentation_id=presentation_id,
                slide_id=scene.slide_id,
                node_id="title",
                new_text="新",
            )
        ],
        presentation_id=presentation_id,
        slide_id=scene.slide_id,
    )

    updated = service.reject_proposal(proposal, notes="defer")

    assert updated.status == ProposalStatus.REJECTED
    assert updated.decided_at is not None
    assert updated.decision is not None
    assert updated.decision.rejected_action_ids == [
        action.action_id for action in proposal.patch_actions
    ]
    assert updated.decision.notes == "defer"
    assert repo.saved is not None
    assert repo.saved.status == ProposalStatus.REJECTED


def test_summarize_patch_action_labels() -> None:
    from archium.application.visual.scene_proposal_service import summarize_patch_action
    from archium.domain.visual.studio_command import build_patch_action

    scene = _scene(_text_node(node_id="title", text="x"))
    action = build_patch_action(
        scene,
        base_scene_hash=compute_scene_hash(scene),
        node_id="title",
        action_type="rewrite_text",
        after_value="y",
    )
    assert summarize_patch_action(action) == "改写文本 `title`"
    assert summarize_patch_action(
        action.model_copy(update={"action_type": "set_overflow_shrink"})
    ) == "文本 `title` 改为自动缩小"
    assert summarize_patch_action(
        action.model_copy(update={"action_type": "custom", "reason": "manual tweak"})
    ) == "manual tweak"


def test_summarize_command_result_statuses() -> None:
    from archium.application.visual.scene_proposal_service import (
        summarize_command_result,
        summarize_command_type,
    )
    from archium.domain.visual.scene_change_proposal import CommandProposalResult
    from archium.domain.visual.studio_command import RewriteTextCommand

    scene = _scene(_text_node(node_id="title", text="旧"))
    presentation_id = uuid4()
    proposal = _proposal_service().create_proposal(
        base_scene=scene,
        commands=[
            RewriteTextCommand(
                presentation_id=presentation_id,
                slide_id=scene.slide_id,
                node_id="title",
                new_text="新",
            )
        ],
        presentation_id=presentation_id,
        slide_id=scene.slide_id,
    )
    command = proposal.commands[0]
    assert summarize_command_type(command) == "改写文本"

    applied = CommandProposalResult(
        command_id=command.command_id,
        status="applied",
        action_ids=[proposal.patch_actions[0].action_id],
    )
    assert "已应用" in summarize_command_result(proposal, applied)

    skipped = CommandProposalResult(command_id=command.command_id, status="skipped")
    assert "已跳过" in summarize_command_result(proposal, skipped)

    failed = CommandProposalResult(
        command_id=command.command_id,
        status="failed",
        issues=[
            __import__(
                "archium.domain.visual.page_quality",
                fromlist=["QualityIssue"],
            ).QualityIssue(
                code="x",
                message="执行失败",
                severity=__import__(
                    "archium.domain.visual.page_quality",
                    fromlist=["IssueSeverity"],
                ).IssueSeverity.MINOR,
                source=QualityIssueSource.AUTO,
            )
        ],
    )
    assert "失败" in summarize_command_result(proposal, failed)


def test_proposal_accept_summary_and_qa_status() -> None:
    from archium.application.visual.scene_deterministic_qa_service import ProposalSceneQAResult
    from archium.application.visual.scene_proposal_service import SceneProposalService
    from archium.domain.visual.page_quality import IssueSeverity, QualityIssue, QualityIssueSource
    from archium.domain.visual.studio_command import RewriteTextCommand

    scene = _scene(_text_node(node_id="title", text="旧"))
    presentation_id = uuid4()
    command = RewriteTextCommand(
        presentation_id=presentation_id,
        slide_id=scene.slide_id,
        node_id="title",
        new_text="新",
    )
    proposal = SceneChangeProposal(
        presentation_id=presentation_id,
        slide_id=scene.slide_id,
        base_scene_hash=compute_scene_hash(scene),
        base_scene=scene,
        proposed_scene=scene,
        commands=[command],
        requested_commands=[command],
        successful_commands=[command],
        patch_actions=[],
        reasons=["提升标题可读性"],
    )
    assert SceneProposalService._proposal_accept_summary(proposal, [command]).startswith("AI 提案：")

    clean_qa = ProposalSceneQAResult(issues=(), layers={}, preview_render_success=True)
    assert SceneProposalService._proposal_qa_status(clean_qa) == "passed"

    warned_qa = ProposalSceneQAResult(
        issues=(
            QualityIssue(
                code="warn",
                message="minor",
                severity=IssueSeverity.MINOR,
                source=QualityIssueSource.AUTO,
            ),
        ),
        layers={},
        preview_render_success=True,
    )
    assert SceneProposalService._proposal_qa_status(warned_qa) == "pass_with_warnings"


def test_apply_patch_actions_geometry_and_visibility() -> None:
    scene = _mixed_scene(
        _drawing_node(node_id="plan"),
        _text_node(node_id="caption", text="长文本", width=2.0, height=0.4),
    )
    plan_action = build_patch_action(
        scene,
        base_scene_hash=compute_scene_hash(scene),
        node_id="plan",
        action_type="enlarge_drawing",
        after_value="0.1,0.2,9.0,5.0",
    )
    patched = apply_patch_actions(scene, [plan_action])
    plan = patched.node_by_id("plan")
    assert isinstance(plan, DrawingNode)
    assert plan.width == 9.0

    visibility_action = build_patch_action(
        patched,
        base_scene_hash=compute_scene_hash(patched),
        node_id="caption",
        action_type="set_node_visibility",
        after_payload={"visible": False},
    )
    lock_action = build_patch_action(
        patched,
        base_scene_hash=compute_scene_hash(patched),
        node_id="caption",
        action_type="set_node_lock",
        after_payload={"locked": True, "lock_scopes": ["geometry"]},
    )
    shrink_action = build_patch_action(
        patched,
        base_scene_hash=compute_scene_hash(patched),
        node_id="caption",
        action_type="set_overflow_shrink",
    )
    patched = apply_patch_actions(
        patched,
        [visibility_action, lock_action, shrink_action],
    )
    caption = patched.node_by_id("caption")
    assert isinstance(caption, TextNode)
    assert caption.visible is False
    assert caption.locked is True
    assert caption.lock_scopes == ["geometry"]
    assert caption.overflow_policy == "shrink"


def test_accept_proposal_rejects_terminal_statuses() -> None:
    from archium.domain.enums import SlideType
    from archium.domain.slide import SlideSpec
    from archium.domain.visual.scene_change_proposal import ProposalDecision

    scene = _scene(_text_node(node_id="title", text="旧"))
    presentation_id = uuid4()
    service = _proposal_service()
    proposal = service.create_proposal(
        base_scene=scene,
        commands=[
            RewriteTextCommand(
                presentation_id=presentation_id,
                slide_id=scene.slide_id,
                node_id="title",
                new_text="新",
            )
        ],
        presentation_id=presentation_id,
        slide_id=scene.slide_id,
    )
    slide = SlideSpec(
        id=scene.slide_id,
        presentation_id=presentation_id,
        title="T",
        slide_type=SlideType.CONTENT,
        order=0,
        chapter_id="ch1",
        message="accept guards",
        layout_plan_id=scene.layout_plan_id,
    )

    rejected = proposal.model_copy(update={"status": ProposalStatus.REJECTED})
    with pytest.raises(WorkflowError, match="已拒绝"):
        service.accept_proposal(rejected, slide)

    accepted = proposal.model_copy(update={"status": ProposalStatus.ACCEPTED})
    with pytest.raises(WorkflowError, match="已被接受"):
        service.accept_proposal(accepted, slide)

    superseded = proposal.model_copy(update={"status": ProposalStatus.SUPERSEDED})
    with pytest.raises(WorkflowError, match="已过期"):
        service.accept_proposal(superseded, slide)

    invalid_decision = ProposalDecision(
        proposal_id=proposal.proposal_id,
        accepted_action_ids=[uuid4()],
    )
    with pytest.raises(WorkflowError, match="至少选择一项"):
        service._resolve_accepted_scene(
            proposal,
            invalid_decision,
        )


def test_count_issues_by_severity_and_remaining_patch_actions() -> None:
    from archium.application.visual.scene_proposal_service import (
        apply_patch_actions,
        count_issues_by_severity,
    )

    scene = _mixed_scene(
        _text_node(node_id="title", text="old", width=2.0, height=0.4),
        _drawing_node(node_id="plan"),
    )
    patched = apply_patch_actions(
        scene,
        [
            build_patch_action(
                scene,
                base_scene_hash=compute_scene_hash(scene),
                node_id="title",
                action_type="delete_node",
                after_value="false",
            ),
            build_patch_action(
                scene,
                base_scene_hash=compute_scene_hash(scene),
                node_id="title",
                action_type="relocate_node",
                after_value="2.5",
            ),
            build_patch_action(
                scene,
                base_scene_hash=compute_scene_hash(scene),
                node_id="title",
                action_type="bump_font_size",
                after_value="18",
            ),
            build_patch_action(
                scene,
                base_scene_hash=compute_scene_hash(scene),
                node_id="plan",
                action_type="set_fit_mode_contain",
            ),
        ],
    )
    title = patched.node_by_id("title")
    plan = patched.node_by_id("plan")
    assert isinstance(title, TextNode)
    assert isinstance(plan, DrawingNode)
    assert title.visible is False
    assert title.y == 2.5
    assert title.font_size >= 18
    assert plan.fit_mode == "contain"

    issues = [
        QualityIssue(code="a", severity=IssueSeverity.MINOR, message="m"),
        QualityIssue(code="b", severity=IssueSeverity.MAJOR, message="M"),
    ]
    assert count_issues_by_severity(issues, IssueSeverity.MAJOR) == 1
