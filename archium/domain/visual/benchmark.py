"""Architectural slide visual benchmark domain models."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Self

from pydantic import Field, field_validator, model_validator

from archium.domain._base import DomainModel

HUMAN_REVIEW_MIN_SCORE = 1
HUMAN_REVIEW_MAX_SCORE = 5
HUMAN_REVIEW_PASS_THRESHOLD = 3.5
HUMAN_REVIEW_FORMAL_AVERAGE_THRESHOLD = 3.8
HUMAN_REVIEW_FORMAL_MIN_ACCEPTED = 24
HUMAN_REVIEW_FORMAL_TOTAL_CASES = 30
HUMAN_REVIEW_PENDING_LABEL = "待人工评审"
HUMAN_REVIEW_INVALIDATED_LABEL = "已作废（需重评）"
LAYOUT_REVIEW_PENDING_LABEL = "待几何评审"
LAYOUT_REVIEW_PASS_THRESHOLD = 3.5
BENCHMARK_VISUAL_REVIEW_REQUIRES_FINAL_RENDER = (
    "人工视觉评审须基于 pptx_render.png（PPTX 真实截图），"
    "且 render_valid=true；不能使用 LayoutPlan 线框图 wireframe.png。"
)
DEFAULT_INVALIDATION_REASON_WIREFRAME = (
    "Reviewed against wireframe preview rather than final rendered slide"
)

HUMAN_REVIEW_WEIGHTS: dict[str, float] = {
    "information_hierarchy": 0.15,
    "visual_focus": 0.15,
    "reading_order": 0.10,
    "image_text_relationship": 0.15,
    "whitespace_density": 0.10,
    "architectural_expression": 0.15,
    "aesthetic_finish": 0.10,
    "editability": 0.10,
}

VISUAL_REVIEW_WEIGHTS: dict[str, float] = {
    "information_hierarchy": 0.17,
    "visual_focus": 0.17,
    "reading_order": 0.11,
    "image_text_relationship": 0.17,
    "whitespace_density": 0.11,
    "architectural_expression": 0.17,
    "aesthetic_finish": 0.10,
}

from archium.domain.visual.enums import LayoutFamily  # noqa: E402


class HumanVisualReviewSource(StrEnum):
    """Provenance for a visual review record."""

    MANUAL = "manual"
    PLACEHOLDER = "placeholder"
    LAYOUT_QA_DERIVED = "layout_qa_derived"
    INVALIDATED = "invalidated"


class ReviewValidity(StrEnum):
    """Whether a stored review may count toward delivery gates."""

    VALID = "valid"
    INVALID_RENDER_ARTIFACT = "invalid_render_artifact"
    SUPERSEDED = "superseded"


_DERIVED_REVIEW_NOTE_MARKERS = (
    "derived from layout",
    "acceptance rehearsal derived",
)
_PLACEHOLDER_REVIEW_NOTE_MARKERS = (
    "占位",
    "待真实",
    "template",
    "placeholder",
)


class ArchitecturalSlideCategory(StrEnum):
    """High-level benchmark page categories (A1–A5)."""

    DRAWING = "drawing"
    PHOTO_ANALYSIS = "photo_analysis"
    CASE_COMPARISON = "case_comparison"
    DATA_METRICS = "data_metrics"
    TEXT_NARRATIVE = "text_narrative"


class BenchmarkCaseDefinition(DomainModel):
    """Metadata describing one architectural slide benchmark case."""

    case_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    category: ArchitecturalSlideCategory
    page_type: str = Field(min_length=1)
    page_task: str = Field(min_length=1)
    visual_focus: str = Field(min_length=1)
    expected_layout_family: LayoutFamily
    allowed_layout_variants: list[str] = Field(min_length=1)
    layout_variant: str = Field(min_length=1)
    chapter_id: str = Field(min_length=1)
    slide_order: int = Field(ge=1)


class HumanVisualReview(DomainModel):
    """Manual visual quality review for one benchmark slide."""

    case_id: str = Field(min_length=1)
    source: HumanVisualReviewSource = HumanVisualReviewSource.MANUAL
    information_hierarchy: int = Field(ge=HUMAN_REVIEW_MIN_SCORE, le=HUMAN_REVIEW_MAX_SCORE)
    visual_focus: int = Field(ge=HUMAN_REVIEW_MIN_SCORE, le=HUMAN_REVIEW_MAX_SCORE)
    reading_order: int = Field(ge=HUMAN_REVIEW_MIN_SCORE, le=HUMAN_REVIEW_MAX_SCORE)
    image_text_relationship: int = Field(ge=HUMAN_REVIEW_MIN_SCORE, le=HUMAN_REVIEW_MAX_SCORE)
    whitespace_density: int = Field(ge=HUMAN_REVIEW_MIN_SCORE, le=HUMAN_REVIEW_MAX_SCORE)
    architectural_expression: int = Field(
        ge=HUMAN_REVIEW_MIN_SCORE, le=HUMAN_REVIEW_MAX_SCORE
    )
    aesthetic_finish: int = Field(ge=HUMAN_REVIEW_MIN_SCORE, le=HUMAN_REVIEW_MAX_SCORE)
    editability: int = Field(ge=HUMAN_REVIEW_MIN_SCORE, le=HUMAN_REVIEW_MAX_SCORE)
    major_problems: list[str] = Field(default_factory=list)
    minor_problems: list[str] = Field(default_factory=list)
    review_completed: bool = False
    accepted_for_delivery: bool = False
    validity: ReviewValidity = ReviewValidity.VALID
    accepted: bool = False
    reviewer: str = ""
    reviewed_at: datetime | None = None
    reviewer_notes: str = ""
    invalidation_reason: str = ""

    @field_validator(
        "information_hierarchy",
        "visual_focus",
        "reading_order",
        "image_text_relationship",
        "whitespace_density",
        "architectural_expression",
        "aesthetic_finish",
        "editability",
    )
    @classmethod
    def _validate_score_range(cls, value: int) -> int:
        if not HUMAN_REVIEW_MIN_SCORE <= value <= HUMAN_REVIEW_MAX_SCORE:
            msg = f"score must be between {HUMAN_REVIEW_MIN_SCORE} and {HUMAN_REVIEW_MAX_SCORE}"
            raise ValueError(msg)
        return value

    def weighted_score(self) -> float:
        """Return the weighted average human score (1–5 scale)."""
        total = 0.0
        weights = VISUAL_REVIEW_WEIGHTS if self.is_manual_review() else HUMAN_REVIEW_WEIGHTS
        for field_name, weight in weights.items():
            if hasattr(self, field_name):
                total += getattr(self, field_name) * weight
        return round(total, 3)

    def passes_threshold(self, threshold: float = HUMAN_REVIEW_PASS_THRESHOLD) -> bool:
        return self.weighted_score() >= threshold

    def human_score_label(self) -> str:
        """User-facing score text; scaffold reviews must not show placeholder numbers."""
        if self.is_invalidated():
            return HUMAN_REVIEW_INVALIDATED_LABEL
        if self.is_scaffold_review():
            return HUMAN_REVIEW_PENDING_LABEL
        return f"{self.weighted_score():.2f}"

    def reportable_weighted_score(self) -> float | None:
        """Return weighted score only for real manual reviews."""
        if self.is_scaffold_review() or self.is_invalidated():
            return None
        return self.weighted_score()

    @model_validator(mode="after")
    def _infer_invalidated_validity(self) -> Self:
        if self.source == HumanVisualReviewSource.INVALIDATED and self.validity == ReviewValidity.VALID:
            object.__setattr__(self, "validity", ReviewValidity.INVALID_RENDER_ARTIFACT)
        return self

    @model_validator(mode="after")
    def _enforce_review_consistency(self) -> Self:
        if self.is_invalidated() or self.validity == ReviewValidity.INVALID_RENDER_ARTIFACT:
            object.__setattr__(self, "accepted_for_delivery", False)
            object.__setattr__(self, "accepted", False)
            if not self.invalidation_reason.strip():
                object.__setattr__(
                    self,
                    "invalidation_reason",
                    DEFAULT_INVALIDATION_REASON_WIREFRAME,
                )
            return self
        if self.is_manual_review():
            if not self.review_completed and self.reviewed_at is not None:
                object.__setattr__(self, "review_completed", True)
            accepted_for_delivery = self.accepted_for_delivery
            accepted = self.accepted
            if self.accepted and not accepted_for_delivery:
                accepted_for_delivery = True
            if accepted_for_delivery and not accepted:
                accepted = True
            if accepted_for_delivery and (self.major_problems or not self.passes_threshold()):
                accepted_for_delivery = False
                accepted = False
            if accepted_for_delivery != self.accepted_for_delivery:
                object.__setattr__(self, "accepted_for_delivery", accepted_for_delivery)
            if accepted != self.accepted:
                object.__setattr__(self, "accepted", accepted)
        return self

    @model_validator(mode="after")
    def _infer_source_from_notes(self) -> Self:
        """Backfill provenance for legacy JSON without an explicit ``source`` field."""
        if self.source != HumanVisualReviewSource.MANUAL:
            return self
        notes = self.reviewer_notes.strip().lower()
        if any(marker in notes for marker in _DERIVED_REVIEW_NOTE_MARKERS):
            return self.model_copy(update={"source": HumanVisualReviewSource.LAYOUT_QA_DERIVED})
        if any(marker in notes for marker in _PLACEHOLDER_REVIEW_NOTE_MARKERS):
            return self.model_copy(update={"source": HumanVisualReviewSource.PLACEHOLDER})
        return self

    def is_manual_review(self) -> bool:
        return self.source == HumanVisualReviewSource.MANUAL

    def is_invalidated(self) -> bool:
        return (
            self.source == HumanVisualReviewSource.INVALIDATED
            or self.validity == ReviewValidity.INVALID_RENDER_ARTIFACT
        )

    def is_scaffold_review(self) -> bool:
        """Return True for placeholder templates and layout-QA-derived stand-ins."""
        return self.source in {
            HumanVisualReviewSource.PLACEHOLDER,
            HumanVisualReviewSource.LAYOUT_QA_DERIVED,
        }


class BenchmarkRenderManifest(DomainModel):
    """Tracks whether a case has a valid final-render preview for visual review."""

    render_source: str = "pending"
    pptx_path: str = "output.pptx"
    image_path: str = "pptx_render.png"
    scene_path: str = "scene.json"
    scene_preview_path: str = "scene_preview.png"
    scene_id: str | None = None
    scene_hash: str = ""
    rendered_at: datetime | None = None
    renderer: str = ""
    asset_count: int = Field(ge=0, default=0)
    real_asset_count: int = Field(ge=0, default=0)
    placeholder_asset_count: int = Field(ge=0, default=0)
    font_fallbacks: list[str] = Field(default_factory=list)
    missing_assets: list[str] = Field(default_factory=list)
    render_valid: bool = False
    notes: str = ""

    def scene_preview_valid(self) -> bool:
        """Return True when a RenderScene preview is ready for Phase 1–2 review."""
        return (
            self.render_valid
            and self.placeholder_asset_count == 0
            and not self.missing_assets
            and bool(self.scene_hash)
        )

    def visual_review_eligible(self) -> bool:
        return (
            self.render_valid
            and self.placeholder_asset_count == 0
            and not self.missing_assets
        )

    def eligibility_blockers(self) -> list[str]:
        blockers: list[str] = []
        if not self.render_valid:
            blockers.append("render_valid=false")
        if self.placeholder_asset_count > 0:
            blockers.append(
                f"placeholder_asset_count={self.placeholder_asset_count} > 0"
            )
        if self.missing_assets:
            blockers.append(f"missing_assets={len(self.missing_assets)}")
        if not self.scene_hash:
            blockers.append("scene_hash missing")
        return blockers


class EditabilityReview(DomainModel):
    """Manual PPTX editability review — separate from visual aesthetics."""

    case_id: str = Field(min_length=1)
    source: HumanVisualReviewSource = HumanVisualReviewSource.MANUAL
    text_editable: int = Field(ge=HUMAN_REVIEW_MIN_SCORE, le=HUMAN_REVIEW_MAX_SCORE)
    image_replaceable: int = Field(ge=HUMAN_REVIEW_MIN_SCORE, le=HUMAN_REVIEW_MAX_SCORE)
    layer_independence: int = Field(ge=HUMAN_REVIEW_MIN_SCORE, le=HUMAN_REVIEW_MAX_SCORE)
    chart_editable: int = Field(ge=HUMAN_REVIEW_MIN_SCORE, le=HUMAN_REVIEW_MAX_SCORE)
    font_usability: int = Field(ge=HUMAN_REVIEW_MIN_SCORE, le=HUMAN_REVIEW_MAX_SCORE)
    not_flattened: int = Field(ge=HUMAN_REVIEW_MIN_SCORE, le=HUMAN_REVIEW_MAX_SCORE)
    selection_ease: int = Field(ge=HUMAN_REVIEW_MIN_SCORE, le=HUMAN_REVIEW_MAX_SCORE)
    modification_ease: int = Field(ge=HUMAN_REVIEW_MIN_SCORE, le=HUMAN_REVIEW_MAX_SCORE)
    major_problems: list[str] = Field(default_factory=list)
    minor_problems: list[str] = Field(default_factory=list)
    review_completed: bool = False
    passed: bool = False
    reviewer: str = ""
    reviewed_at: datetime | None = None
    reviewer_notes: str = ""

    def weighted_score(self) -> float:
        weights = {
            "text_editable": 0.20,
            "image_replaceable": 0.15,
            "layer_independence": 0.15,
            "chart_editable": 0.10,
            "font_usability": 0.10,
            "not_flattened": 0.15,
            "selection_ease": 0.075,
            "modification_ease": 0.075,
        }
        total = sum(getattr(self, field) * weight for field, weight in weights.items())
        return round(total, 3)

    def passes_threshold(self, threshold: float = HUMAN_REVIEW_PASS_THRESHOLD) -> bool:
        return self.weighted_score() >= threshold

    def is_manual_review(self) -> bool:
        return self.source == HumanVisualReviewSource.MANUAL

    @model_validator(mode="after")
    def _enforce_pass_consistency(self) -> Self:
        if self.is_manual_review() and self.passed and (
            self.major_problems or not self.passes_threshold()
        ):
            object.__setattr__(self, "passed", False)
        return self


class HumanLayoutReview(DomainModel):
    """Manual layout-geometry review against wireframe.png (not final render)."""

    case_id: str = Field(min_length=1)
    source: HumanVisualReviewSource = HumanVisualReviewSource.MANUAL
    information_hierarchy: int = Field(ge=HUMAN_REVIEW_MIN_SCORE, le=HUMAN_REVIEW_MAX_SCORE)
    reading_order: int = Field(ge=HUMAN_REVIEW_MIN_SCORE, le=HUMAN_REVIEW_MAX_SCORE)
    whitespace_density: int = Field(ge=HUMAN_REVIEW_MIN_SCORE, le=HUMAN_REVIEW_MAX_SCORE)
    spatial_balance: int = Field(ge=HUMAN_REVIEW_MIN_SCORE, le=HUMAN_REVIEW_MAX_SCORE)
    layout_clarity: int = Field(ge=HUMAN_REVIEW_MIN_SCORE, le=HUMAN_REVIEW_MAX_SCORE)
    major_problems: list[str] = Field(default_factory=list)
    minor_problems: list[str] = Field(default_factory=list)
    accepted_for_geometry: bool = False
    reviewer: str = ""
    reviewed_at: datetime | None = None
    reviewer_notes: str = ""

    def weighted_score(self) -> float:
        weights = {
            "information_hierarchy": 0.25,
            "reading_order": 0.25,
            "whitespace_density": 0.20,
            "spatial_balance": 0.15,
            "layout_clarity": 0.15,
        }
        total = sum(getattr(self, field) * weight for field, weight in weights.items())
        return round(total, 3)

    def passes_threshold(self, threshold: float = LAYOUT_REVIEW_PASS_THRESHOLD) -> bool:
        return self.weighted_score() >= threshold

    def human_score_label(self) -> str:
        if self.is_scaffold_review():
            return LAYOUT_REVIEW_PENDING_LABEL
        return f"{self.weighted_score():.2f}"

    def is_manual_review(self) -> bool:
        return self.source == HumanVisualReviewSource.MANUAL

    def is_scaffold_review(self) -> bool:
        return self.source in {
            HumanVisualReviewSource.PLACEHOLDER,
            HumanVisualReviewSource.LAYOUT_QA_DERIVED,
        }

    @model_validator(mode="after")
    def _enforce_geometry_consistency(self) -> Self:
        if self.is_manual_review() and self.accepted_for_geometry and (
            self.major_problems or not self.passes_threshold()
        ):
            self.accepted_for_geometry = False
        return self


class BenchmarkPendingCase(DomainModel):
    """Case awaiting manual review — metadata only, no scores."""

    case_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    category: str = Field(min_length=1)
    page_type: str = Field(min_length=1)
    preview_png: str = ""


class BenchmarkHumanReviewExport(DomainModel):
    """Deck-level export bundle for benchmark manual reviews (backup / offline handoff)."""

    bundle_version: int = 1
    exported_at: datetime
    case_count: int = Field(ge=0)
    manual_review_count: int = Field(ge=0)
    pending_count: int = Field(ge=0)
    reviews: list[HumanVisualReview] = Field(default_factory=list)
    pending_cases: list[BenchmarkPendingCase] = Field(default_factory=list)
    human_quality_gate_passed: bool = False
    human_average_weighted_score: float | None = None
    human_quality_gate_reasons: list[str] = Field(default_factory=list)


class BenchmarkRuleScore(DomainModel):
    """Automated rule-based score for a benchmark case."""

    case_id: str
    layout_valid: bool
    layout_score: float
    has_critical: bool
    blocking_issue_count: int
    rule_codes: list[str] = Field(default_factory=list)
    deck_qa_score: float | None = None
    passed: bool = False
