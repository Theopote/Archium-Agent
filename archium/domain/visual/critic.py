"""Screenshot / page Visual Critic models — Visual Quality, not Layout Quality.

Read-only evaluation of composed pages. Never drives LayoutRepairService.
"""

from __future__ import annotations

from pydantic import Field, computed_field

from archium.domain._base import DomainModel
from archium.domain.visual.enums import LayoutIssueSeverity

# Stable critic rule codes (Visual Quality namespace — not LAYOUT.* / asset VISUAL.*).
CRITIC_FOCUS_UNCLEAR = "CRITIC.FOCUS_UNCLEAR"
CRITIC_READING_ORDER_AWKWARD = "CRITIC.READING_ORDER_AWKWARD"
CRITIC_HERO_WEAK = "CRITIC.HERO_WEAK"
CRITIC_COLOR_CHAOS = "CRITIC.COLOR_CHAOS"
CRITIC_MECHANICAL = "CRITIC.MECHANICAL"
CRITIC_PAGE_REPETITION = "CRITIC.PAGE_REPETITION"
CRITIC_TEMPLATE_BRIEF_VIOLATION = "CRITIC.TEMPLATE_BRIEF_VIOLATION"
# v0.3 screenshot / structure critic
CRITIC_TITLE_WEAK = "CRITIC.TITLE_WEAK"
CRITIC_COPY_DENSITY_HIGH = "CRITIC.COPY_DENSITY_HIGH"
CRITIC_WHITESPACE_WEAK = "CRITIC.WHITESPACE_WEAK"
CRITIC_ALIGNMENT_DRIFT = "CRITIC.ALIGNMENT_DRIFT"
CRITIC_BALANCE_OFF = "CRITIC.BALANCE_OFF"
CRITIC_VISUAL_NOISE_HIGH = "CRITIC.VISUAL_NOISE_HIGH"
CRITIC_TENSION_FLAT = "CRITIC.TENSION_FLAT"


class VisualCriticFinding(DomainModel):
    """One read-only Visual Critic observation."""

    rule_code: str = Field(min_length=1)
    severity: LayoutIssueSeverity = LayoutIssueSeverity.WARNING
    message: str = Field(min_length=1)
    suggestion: str | None = None
    evidence: dict[str, object] = Field(default_factory=dict)


class VisualCriticDimensions(DomainModel):
    """Per-dimension Visual Quality scores in [0, 1]. None = skipped."""

    focus_hierarchy_clarity: float | None = Field(default=None, ge=0.0, le=1.0)
    reading_order_naturalness: float | None = Field(default=None, ge=0.0, le=1.0)
    hero_prominence: float | None = Field(default=None, ge=0.0, le=1.0)
    color_chaos: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="1.0 = calm palette; 0.0 = chaotic (inverted chaos).",
    )
    mechanical_feel: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="1.0 = organic; 0.0 = mechanical grid feel.",
    )
    multi_page_repetition: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="1.0 = varied; 0.0 = near-duplicate pages.",
    )
    balance: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="1.0 = stable visual mass distribution; 0.0 = lopsided.",
    )
    whitespace: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="1.0 = controlled breathing room; 0.0 = too dense or too empty.",
    )
    tension: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="1.0 = intentional contrast; 0.0 = flat visual energy.",
    )
    alignment: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="1.0 = disciplined shared edges; 0.0 = drifting alignment.",
    )
    visual_noise: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="1.0 = calm and restrained; 0.0 = noisy / cluttered.",
    )


class VisualCriticReport(DomainModel):
    """Visual Quality critique for one slide / page image.

    Distinct from LayoutValidationReport / LayoutScore (Layout Quality).
    """

    score_kind: str = Field(default="visual_quality")
    method: str = Field(default="heuristic_v0", min_length=1)
    layout_plan_id: str | None = None
    slide_id: str | None = None
    source_image: str | None = None
    dimensions: VisualCriticDimensions = Field(default_factory=VisualCriticDimensions)
    findings: list[VisualCriticFinding] = Field(default_factory=list)
    total_score: float | None = Field(default=None, ge=0.0, le=1.0)
    notes: list[str] = Field(default_factory=list)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def finding_codes(self) -> list[str]:
        return sorted({item.rule_code for item in self.findings})
