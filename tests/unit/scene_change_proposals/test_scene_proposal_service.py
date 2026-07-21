"""Unit tests for SceneChangeProposal workflow."""

from __future__ import annotations

from uuid import uuid4

from archium.application.visual.scene_proposal_qa import compare_proposal_qa
from archium.application.visual.scene_proposal_service import (
    SceneProposalService,
    apply_patch_actions,
)
from archium.domain.visual.page_quality import IssueSeverity, QualityIssue, QualityIssueSource
from archium.domain.visual.render_scene import BackgroundStyle, RenderScene, TextNode
from archium.domain.visual.scene_change_proposal import ProposalStatus
from archium.domain.visual.scene_qa import SceneSemanticCheckCode
from archium.domain.visual.studio_command import RewriteTextCommand
from archium.exceptions import WorkflowError


def _text_node(
    *,
    node_id: str,
    text: str,
    width: float = 2.0,
    height: float = 0.4,
    overflow: str = "error",
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
    from archium.domain.visual.studio_command import ScenePatchAction

    patched = apply_patch_actions(
        scene,
        [
            ScenePatchAction(
                scene_id=scene.slide_id,
                node_id="title",
                action_type="rewrite_text",
                after_value="新",
            )
        ],
    )
    node = patched.node_by_id("title")
    assert isinstance(node, TextNode)
    assert node.text == "新"


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
