"""VQ-007: Bounded Visual Critic refinements — allowlisted patches only.

Critic remains read-only for diagnosis. This module defines the *only* actions
a refinement loop may apply. No free-form rewrite, no LayoutRepairService.
"""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import Field

from archium.domain._base import DomainModel
from archium.domain.visual.critic import VisualCriticReport
from archium.domain.visual.render_scene import RenderScene

# Hard caps — product contract for "有限精修".
MAX_REFINEMENT_ROUNDS = 2
DEFAULT_REFINEMENT_ROUNDS = 1
MAX_ACTIONS_PER_PAGE = 3
MAX_ACTIONS_PER_DECK = 24


class VisualRefinementActionType(StrEnum):
    """Allowlisted scene patches derived from Visual Critic findings."""

    BOOST_TITLE_SCALE = "boost_title_scale"
    ENLARGE_HERO = "enlarge_hero"
    SOFTEN_SECONDARY_TEXT = "soften_secondary_text"
    QUIET_MOTIF = "quiet_motif"
    TRIM_BODY_BOX = "trim_body_box"
    SOFTEN_ACCENT_SHAPES = "soften_accent_shapes"
    FIX_TEXT_CONTRAST = "fix_text_contrast"


# Which critic codes may propose which actions (closed map).
CRITIC_CODE_TO_ACTIONS: dict[str, tuple[VisualRefinementActionType, ...]] = {
    "CRITIC.TITLE_WEAK": (VisualRefinementActionType.BOOST_TITLE_SCALE,),
    "CRITIC.FOCUS_UNCLEAR": (
        VisualRefinementActionType.BOOST_TITLE_SCALE,
        VisualRefinementActionType.QUIET_MOTIF,
    ),
    "CRITIC.HERO_WEAK": (VisualRefinementActionType.ENLARGE_HERO,),
    "CRITIC.COPY_DENSITY_HIGH": (
        VisualRefinementActionType.SOFTEN_SECONDARY_TEXT,
        VisualRefinementActionType.TRIM_BODY_BOX,
    ),
    "CRITIC.VISUAL_NOISE_HIGH": (VisualRefinementActionType.QUIET_MOTIF,),
    "CRITIC.TENSION_FLAT": (
        VisualRefinementActionType.BOOST_TITLE_SCALE,
        VisualRefinementActionType.ENLARGE_HERO,
    ),
    "CRITIC.WHITESPACE_WEAK": (VisualRefinementActionType.TRIM_BODY_BOX,),
    "CRITIC.COLOR_CHAOS": (VisualRefinementActionType.SOFTEN_ACCENT_SHAPES,),
    "CRITIC.MECHANICAL": (VisualRefinementActionType.QUIET_MOTIF,),
    "CRITIC.TEXT_CONTRAST_LOW": (VisualRefinementActionType.FIX_TEXT_CONTRAST,),
}


class VisualRefinementAction(DomainModel):
    """One allowlisted patch proposed or applied to a RenderScene."""

    action_type: VisualRefinementActionType
    rule_code: str = Field(min_length=1)
    target_node_id: str | None = None
    magnitude: float = Field(
        default=0.12,
        ge=0.0,
        le=0.5,
        description="Relative change (e.g. 0.12 = +12% title scale).",
    )
    reason: str = ""
    applied: bool = False


class VisualRefinementProposal(DomainModel):
    """Critic→patch proposal for one page (not yet applied)."""

    slide_id: str | None = None
    layout_plan_id: str | None = None
    source_score: float | None = None
    actions: list[VisualRefinementAction] = Field(default_factory=list)
    deferred_codes: list[str] = Field(
        default_factory=list,
        description="Critic codes with no allowlisted action.",
    )


class VisualRefinementRound(DomainModel):
    """One evaluate → propose → apply cycle."""

    round_index: int = Field(ge=0)
    before_score: float | None = None
    after_score: float | None = None
    proposed: list[VisualRefinementAction] = Field(default_factory=list)
    applied: list[VisualRefinementAction] = Field(default_factory=list)
    stopped_reason: str | None = None


class VisualRefinementLoopResult(DomainModel):
    """Bounded refinement loop output for one page."""

    scene: RenderScene
    before_report: VisualCriticReport | None = None
    after_report: VisualCriticReport | None = None
    proposal: VisualRefinementProposal | None = None
    rounds: list[VisualRefinementRound] = Field(default_factory=list)
    applied_count: int = Field(default=0, ge=0)
    stopped_reason: str = "completed"

    @property
    def improved(self) -> bool:
        if self.before_report is None or self.after_report is None:
            return self.applied_count > 0
        before = self.before_report.total_score
        after = self.after_report.total_score
        if before is None or after is None:
            return self.applied_count > 0
        return after >= before


class VisualRefinementDeckResult(DomainModel):
    """Deck-level VQ-007 loop summary."""

    page_results: list[VisualRefinementLoopResult] = Field(default_factory=list)
    total_applied: int = Field(default=0, ge=0)
    pages_touched: int = Field(default=0, ge=0)
    presentation_id: UUID | None = None
    notes: list[str] = Field(default_factory=list)


__all__ = [
    "CRITIC_CODE_TO_ACTIONS",
    "DEFAULT_REFINEMENT_ROUNDS",
    "MAX_ACTIONS_PER_DECK",
    "MAX_ACTIONS_PER_PAGE",
    "MAX_REFINEMENT_ROUNDS",
    "VisualRefinementAction",
    "VisualRefinementActionType",
    "VisualRefinementDeckResult",
    "VisualRefinementLoopResult",
    "VisualRefinementProposal",
    "VisualRefinementRound",
]
