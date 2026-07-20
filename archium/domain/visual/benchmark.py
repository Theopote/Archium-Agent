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

from archium.domain.visual.enums import LayoutFamily  # noqa: E402

class HumanVisualReviewSource(StrEnum):
    """Provenance for a visual review record."""

    MANUAL = "manual"
    PLACEHOLDER = "placeholder"
    LAYOUT_QA_DERIVED = "layout_qa_derived"


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
    accepted: bool = False
    reviewer: str = ""
    reviewed_at: datetime | None = None
    reviewer_notes: str = ""

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
        for field_name, weight in HUMAN_REVIEW_WEIGHTS.items():
            total += getattr(self, field_name) * weight
        return round(total, 3)

    def passes_threshold(self, threshold: float = HUMAN_REVIEW_PASS_THRESHOLD) -> bool:
        return self.weighted_score() >= threshold

    def human_score_label(self) -> str:
        """User-facing score text; scaffold reviews must not show placeholder numbers."""
        if self.is_scaffold_review():
            return HUMAN_REVIEW_PENDING_LABEL
        return f"{self.weighted_score():.2f}"

    def reportable_weighted_score(self) -> float | None:
        """Return weighted score only for real manual reviews."""
        if self.is_scaffold_review():
            return None
        return self.weighted_score()

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

    def is_scaffold_review(self) -> bool:
        """Return True for placeholder templates and layout-QA-derived stand-ins."""
        return self.source in {
            HumanVisualReviewSource.PLACEHOLDER,
            HumanVisualReviewSource.LAYOUT_QA_DERIVED,
        }


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
