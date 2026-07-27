"""QD-003 — Accept must reject residual (not only introduced) blockers."""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from archium.application.visual.scene_deterministic_qa_service import ProposalSceneQAResult
from archium.application.visual.scene_proposal_qa import (
    compare_proposal_qa,
    proposal_has_open_blocker,
    proposal_introduces_blocker,
)
from archium.application.visual.scene_proposal_service import SceneProposalService
from archium.domain.slide import SlideSpec
from archium.domain.visual.page_quality import (
    IssueCategory,
    IssueSeverity,
    QualityIssue,
    QualityIssueSource,
)
from archium.domain.visual.render_scene import (
    BackgroundStyle,
    RenderScene,
    TextNode,
    compute_scene_hash,
)
from archium.domain.visual.scene_change_proposal import SceneChangeProposal
from archium.domain.visual.studio_command import RewriteTextCommand
from archium.exceptions import WorkflowError


def _issue(
    code: str,
    severity: IssueSeverity,
    *,
    evidence: list[str] | None = None,
) -> QualityIssue:
    return QualityIssue(
        code=code,
        severity=severity,
        category=IssueCategory.LAYOUT_VISUAL,
        message=code,
        evidence=list(evidence or []),
        source=QualityIssueSource.AUTO,
    )


def test_proposal_has_open_blocker_true_for_remaining() -> None:
    blocker = _issue("SEMANTIC.TEXT_OVERFLOW", IssueSeverity.BLOCKER, evidence=["n1"])
    comparison = compare_proposal_qa([blocker], [blocker])
    assert comparison.introduced == []
    assert comparison.remaining
    assert not proposal_introduces_blocker(comparison)
    assert proposal_has_open_blocker(comparison)


def test_proposal_has_open_blocker_true_for_introduced() -> None:
    before = [_issue("warn", IssueSeverity.MINOR)]
    after = before + [_issue("SEMANTIC.TEXT_OVERFLOW", IssueSeverity.BLOCKER, evidence=["n1"])]
    comparison = compare_proposal_qa(before, after)
    assert proposal_introduces_blocker(comparison)
    assert proposal_has_open_blocker(comparison)


def test_proposal_has_open_blocker_false_when_major_only() -> None:
    before = [_issue("SEMANTIC.TEXT_OVERFLOW", IssueSeverity.BLOCKER, evidence=["n1"])]
    after = [_issue("layout.tight", IssueSeverity.MAJOR, evidence=["n1"])]
    comparison = compare_proposal_qa(before, after)
    assert comparison.resolved
    assert not proposal_has_open_blocker(comparison)
    assert not proposal_introduces_blocker(comparison)


def test_accept_proposal_rejects_remaining_blocker() -> None:
    scene = RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=10,
        page_height=5.625,
        background=BackgroundStyle(color="#FFFFFF"),
        nodes=[
            TextNode(
                id="title",
                x=0.5,
                y=1.0,
                width=2.0,
                height=0.4,
                z_index=1,
                text="标题",
                font_family="Arial",
                font_size=12,
                color="#000000",
                line_height=1.2,
            )
        ],
    )
    presentation_id = uuid4()
    command = RewriteTextCommand(
        presentation_id=presentation_id,
        slide_id=scene.slide_id,
        node_id="title",
        new_text="新标题",
    )
    residual = _issue("SEMANTIC.TEXT_OVERFLOW", IssueSeverity.BLOCKER, evidence=["title"])
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
        qa_before=[residual],
        qa_after=[residual],
    )
    slide = SlideSpec(
        presentation_id=presentation_id,
        chapter_id="ch-1",
        order=0,
        title="页",
        message="内容",
    )
    service = SceneProposalService.__new__(SceneProposalService)
    service._qa_for_scene = MagicMock(  # type: ignore[method-assign]
        return_value=ProposalSceneQAResult(
            issues=(residual,),
            layers={},
            preview_render_success=True,
        )
    )
    service._persist_scene = MagicMock()  # type: ignore[method-assign]

    with pytest.raises(WorkflowError, match="Blocker"):
        service.accept_proposal(proposal, slide, current_scene=scene)

    service._persist_scene.assert_not_called()
