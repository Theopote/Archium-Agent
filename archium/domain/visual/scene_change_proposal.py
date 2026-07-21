"""AI scene change proposals — before/after candidate scenes with QA diff."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import Field

from archium.domain._base import DomainModel, TimestampedModel, new_uuid, utc_now
from archium.domain.visual.page_quality import QualityIssue
from archium.domain.visual.render_scene import RenderScene
from archium.domain.visual.studio_command import ScenePatchAction, StudioCommand


class ProposalStatus(StrEnum):
    DRAFT = "draft"
    READY = "ready"
    ACCEPTED = "accepted"
    PARTIALLY_ACCEPTED = "partially_accepted"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


SceneRevisionSource = Literal[
    "manual",
    "ai_proposal",
    "automatic_repair",
    "template_application",
]


class SceneChangeProposal(DomainModel):
    """A reviewable before/after scene mutation with command traceability."""

    proposal_id: UUID = Field(default_factory=new_uuid)
    presentation_id: UUID
    slide_id: UUID

    base_revision_id: UUID | None = None
    base_scene_hash: str = Field(min_length=1)
    base_scene: RenderScene
    proposed_scene: RenderScene

    commands: list[StudioCommand] = Field(default_factory=list)
    patch_actions: list[ScenePatchAction] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)

    qa_before: list[QualityIssue] = Field(default_factory=list)
    qa_after: list[QualityIssue] = Field(default_factory=list)

    status: ProposalStatus = ProposalStatus.READY
    created_at: datetime = Field(default_factory=utc_now)


class ProposalDecision(DomainModel):
    """User decision on a scene change proposal."""

    proposal_id: UUID
    accepted_action_ids: list[UUID] = Field(default_factory=list)
    rejected_action_ids: list[UUID] = Field(default_factory=list)
    notes: str = ""


class SceneRevision(TimestampedModel):
    """Accepted scene snapshot linked to revision history."""

    revision_id: UUID = Field(default_factory=new_uuid)
    parent_revision_id: UUID | None = None
    slide_id: UUID
    scene_id: UUID
    source: SceneRevisionSource = "ai_proposal"
    scene_hash: str = Field(min_length=1)
    commands: list[StudioCommand] = Field(default_factory=list)


class ProposalQAComparison(DomainModel):
    """QA diff between proposal before and after scenes."""

    before: list[QualityIssue] = Field(default_factory=list)
    after: list[QualityIssue] = Field(default_factory=list)
    resolved: list[QualityIssue] = Field(default_factory=list)
    remaining: list[QualityIssue] = Field(default_factory=list)
    introduced: list[QualityIssue] = Field(default_factory=list)

    @property
    def before_major_count(self) -> int:
        return _count_major_blocker(self.before)

    @property
    def after_major_count(self) -> int:
        return _count_major_blocker(self.after)


def _count_major_blocker(issues: list[QualityIssue]) -> int:
    from archium.domain.visual.page_quality import IssueSeverity

    return sum(
        1
        for issue in issues
        if issue.severity in {IssueSeverity.MAJOR, IssueSeverity.BLOCKER}
    )
