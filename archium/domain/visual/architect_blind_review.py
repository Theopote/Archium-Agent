"""VQ-008 — Architect Blind Review Benchmark (Beta hard gate).

Blind materials are unlabeled A/B/C among:
  - archium_legacy (旧版)
  - archium_current (新版)
  - human_reference (人工优秀参考)

Reviewers never see source labels. Metrics unseal after ballots are collected.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import Field, field_validator, model_validator

from archium.domain._base import DomainModel

# --- Product thresholds (P0 VQR §6) ---
VQ008_MIN_REVIEWERS = 5
VQ008_NEW_VS_OLD_WIN_RATE = 0.80
VQ008_READY_OR_LIGHT_EDIT_RATE = 0.60
VQ008_MEAN_VISUAL_SCORE = 7.0  # on 1–10 scale
VQ008_EDIT_TIME_REDUCTION_RATE = 0.50
VQ008_PROTOCOL_VERSION = "vq8.1"

# Aesthetic dimensions required by P0 (score each 1–10 when collected).
VQ008_DIMENSIONS: tuple[str, ...] = (
    "hierarchy",
    "focal_clarity",
    "typography_expressiveness",
    "color_harmony",
    "graphic_coherence",
    "composition_tension",
    "image_treatment",
    "architectural_relevance",
    "deck_rhythm",
    "template_repetition",
)


class BlindSourceKind(StrEnum):
    ARCHIUM_LEGACY = "archium_legacy"
    ARCHIUM_CURRENT = "archium_current"
    HUMAN_REFERENCE = "human_reference"


class BlindReadiness(StrEnum):
    """Delivery readiness for one anonymized stimulus."""

    READY = "ready"  # 可直接使用
    LIGHT_EDIT = "light_edit"  # 轻微修改
    HEAVY_EDIT = "heavy_edit"
    REJECT = "reject"


class BlindStimulus(DomainModel):
    """One anonymized slide image in a trial."""

    label: str = Field(min_length=1, max_length=8, description="Shown to reviewer (A/B/C).")
    true_source: BlindSourceKind
    case_id: str = Field(min_length=1)
    asset_path: str | None = None
    notes: str = ""


class BlindTrial(DomainModel):
    """One blind comparison unit (typically three unlabeled stimuli)."""

    trial_id: str = Field(min_length=1)
    case_id: str = Field(min_length=1)
    title: str = ""
    stimuli: list[BlindStimulus] = Field(min_length=2)
    page_kind: str = ""

    @model_validator(mode="after")
    def _unique_labels(self) -> BlindTrial:
        labels = [s.label for s in self.stimuli]
        if len(labels) != len(set(labels)):
            raise ValueError("BlindTrial stimuli labels must be unique")
        sources = [s.true_source for s in self.stimuli]
        if BlindSourceKind.ARCHIUM_CURRENT not in sources:
            raise ValueError("BlindTrial must include archium_current")
        if BlindSourceKind.ARCHIUM_LEGACY not in sources:
            raise ValueError("BlindTrial must include archium_legacy")
        return self

    def source_for_label(self, label: str) -> BlindSourceKind | None:
        for stimulus in self.stimuli:
            if stimulus.label == label:
                return stimulus.true_source
        return None

    def label_for_source(self, source: BlindSourceKind) -> str | None:
        for stimulus in self.stimuli:
            if stimulus.true_source == source:
                return stimulus.label
        return None


class BlindBallot(DomainModel):
    """One architect's sealed ratings for one trial (labels only — no sources)."""

    ballot_id: str = Field(default_factory=lambda: str(uuid4()))
    reviewer_id: str = Field(min_length=1)
    trial_id: str = Field(min_length=1)
    ranking_labels: list[str] = Field(
        min_length=1,
        description="Best → worst anonymized labels.",
    )
    readiness_by_label: dict[str, BlindReadiness] = Field(default_factory=dict)
    visual_score_by_label: dict[str, float] = Field(
        default_factory=dict,
        description="Overall visual quality 1–10 per label.",
    )
    edit_minutes_by_label: dict[str, float] = Field(
        default_factory=dict,
        description="Estimated minutes to make page client-ready.",
    )
    dimension_scores_by_label: dict[str, dict[str, float]] = Field(
        default_factory=dict,
        description="Optional per-dimension 1–10 scores keyed by VQ008_DIMENSIONS.",
    )
    preferred_label: str | None = None
    reviewed_at: datetime | None = None
    notes: str = ""

    @field_validator("visual_score_by_label")
    @classmethod
    def _scores_in_range(cls, value: dict[str, float]) -> dict[str, float]:
        for label, score in value.items():
            if not 1.0 <= float(score) <= 10.0:
                raise ValueError(f"visual score for {label} must be in [1, 10]")
        return value

    @model_validator(mode="after")
    def _preferred_defaults_to_rank_head(self) -> BlindBallot:
        if not self.preferred_label and self.ranking_labels:
            object.__setattr__(self, "preferred_label", self.ranking_labels[0])
        return self


class BlindReviewSession(DomainModel):
    """Full blind-review campaign: trials + ballots + sealed key."""

    session_id: UUID = Field(default_factory=uuid4)
    protocol_version: str = VQ008_PROTOCOL_VERSION
    title: str = "VQ-008 Architect Blind Review"
    min_reviewers: int = Field(default=VQ008_MIN_REVIEWERS, ge=1)
    trials: list[BlindTrial] = Field(default_factory=list)
    ballots: list[BlindBallot] = Field(default_factory=list)
    created_at: datetime | None = None
    notes: list[str] = Field(default_factory=list)

    def trial_by_id(self, trial_id: str) -> BlindTrial | None:
        return next((t for t in self.trials if t.trial_id == trial_id), None)

    def reviewer_ids(self) -> list[str]:
        return sorted({b.reviewer_id for b in self.ballots})


class BlindReviewMetrics(DomainModel):
    """Unsealed aggregate metrics for the Beta gate."""

    protocol_version: str = VQ008_PROTOCOL_VERSION
    session_id: UUID | None = None
    reviewer_count: int = 0
    ballot_count: int = 0
    trial_count: int = 0
    new_vs_old_comparisons: int = 0
    new_vs_old_wins: int = 0
    new_vs_old_win_rate: float | None = None
    current_readiness_samples: int = 0
    current_ready_or_light: int = 0
    ready_or_light_edit_rate: float | None = None
    current_score_samples: int = 0
    mean_visual_score_current: float | None = None
    edit_time_pairs: int = 0
    mean_edit_minutes_legacy: float | None = None
    mean_edit_minutes_current: float | None = None
    edit_time_reduction_rate: float | None = None
    dimension_means_current: dict[str, float] = Field(default_factory=dict)
    passed: bool = False
    reasons: list[str] = Field(default_factory=list)
    thresholds: dict[str, float] = Field(
        default_factory=lambda: {
            "min_reviewers": float(VQ008_MIN_REVIEWERS),
            "new_vs_old_win_rate": VQ008_NEW_VS_OLD_WIN_RATE,
            "ready_or_light_edit_rate": VQ008_READY_OR_LIGHT_EDIT_RATE,
            "mean_visual_score": VQ008_MEAN_VISUAL_SCORE,
            "edit_time_reduction_rate": VQ008_EDIT_TIME_REDUCTION_RATE,
        }
    )


class BlindReviewGateResult(DomainModel):
    """Beta hard-gate outcome for VQ-008."""

    passed: bool
    metrics: BlindReviewMetrics
    blocking_reasons: list[str] = Field(default_factory=list)
    beta_allowed: bool = False

    def summary(self) -> str:
        if self.passed and self.beta_allowed:
            return "VQ-008 Architect Blind Review: PASSED — Beta visual gate clear"
        reasons = self.blocking_reasons or self.metrics.reasons
        return "VQ-008 FAILED: " + ("; ".join(reasons) if reasons else "thresholds not met")


__all__ = [
    "VQ008_DIMENSIONS",
    "VQ008_EDIT_TIME_REDUCTION_RATE",
    "VQ008_MEAN_VISUAL_SCORE",
    "VQ008_MIN_REVIEWERS",
    "VQ008_NEW_VS_OLD_WIN_RATE",
    "VQ008_PROTOCOL_VERSION",
    "VQ008_READY_OR_LIGHT_EDIT_RATE",
    "BlindBallot",
    "BlindReadiness",
    "BlindReviewGateResult",
    "BlindReviewMetrics",
    "BlindReviewSession",
    "BlindSourceKind",
    "BlindStimulus",
    "BlindTrial",
]
