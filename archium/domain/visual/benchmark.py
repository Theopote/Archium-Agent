"""Architectural slide visual benchmark domain models."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field, field_validator

from archium.domain._base import DomainModel
from archium.domain.visual.enums import LayoutFamily

HUMAN_REVIEW_MIN_SCORE = 1
HUMAN_REVIEW_MAX_SCORE = 5
HUMAN_REVIEW_PASS_THRESHOLD = 3.5

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
