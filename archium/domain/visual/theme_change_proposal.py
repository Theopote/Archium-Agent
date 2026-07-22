"""Theme change proposals — deck-wide DesignSystem mutations with QA preview."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import Field

from archium.domain._base import DomainModel, new_uuid, utc_now
from archium.domain.visual.deck_theme_tokens import DeckThemeTokens
from archium.domain.visual.design_system import DesignSystem
from archium.domain.visual.page_quality import QualityIssue


class ThemeProposalStatus(StrEnum):
    DRAFT = "draft"
    READY = "ready"
    READY_WITH_WARNINGS = "ready_with_warnings"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class ThemeProposalDecision(DomainModel):
    """User decision on a theme change proposal."""

    proposal_id: UUID
    notes: str = ""


class ThemeDeckImpactStats(DomainModel):
    """Full-deck impact preview shown before accepting a theme proposal."""

    affected_pages: int = 0
    font_changes: int = 0
    background_changes: int = 0
    drawing_node_changes: int = 0
    evidence_photo_changes: int = 0
    warnings: int = 0
    blockers: int = 0


class ThemeChangeProposal(DomainModel):
    """Reviewable before/after DesignSystem change for an entire presentation.

    Accept switches ``ArtDirection.design_system_id`` and re-resolves scenes from
    token references — it must not bake theme colors into every node via
    per-slide SceneRevision spam.
    """

    proposal_id: UUID = Field(default_factory=new_uuid)
    presentation_id: UUID
    art_direction_id: UUID | None = None

    base_design_system_id: UUID | None = None
    proposed_design_system_id: UUID | None = None
    base_design_system: DesignSystem
    proposed_design_system: DesignSystem
    token_patch: DeckThemeTokens

    sample_slide_ids: list[UUID] = Field(default_factory=list)
    # slide_id → human/agent-readable reason (cover / drawing_focus / …)
    sample_selection_reason: dict[str, str] = Field(default_factory=dict)
    preview_scene_hashes: dict[str, str] = Field(default_factory=dict)
    qa_by_slide: dict[str, list[QualityIssue]] = Field(default_factory=dict)
    qa_summary: list[QualityIssue] = Field(default_factory=list)
    deck_impact: ThemeDeckImpactStats = Field(default_factory=ThemeDeckImpactStats)

    status: ThemeProposalStatus = ThemeProposalStatus.READY
    decision: ThemeProposalDecision | None = None
    decided_at: datetime | None = None
    created_at: datetime = Field(default_factory=utc_now)
