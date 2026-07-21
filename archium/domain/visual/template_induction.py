"""Template induction classification and clustering models (Phase 0–3)."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal
from uuid import uuid4

from pydantic import Field

from archium.domain._base import DomainModel, IdentifiedModel, TimestampedModel


class FunctionalSlideType(StrEnum):
    COVER = "cover"
    AGENDA = "agenda"
    SECTION_DIVIDER = "section_divider"
    EXECUTIVE_SUMMARY = "executive_summary"
    DECISION = "decision"
    CONTENT = "content"
    CLOSING = "closing"
    APPENDIX = "appendix"
    UNKNOWN = "unknown"


class ArchitecturalContentType(StrEnum):
    DRAWING_FOCUS = "drawing_focus"
    PHOTO_ANALYSIS = "photo_analysis"
    CASE_COMPARISON = "case_comparison"
    BEFORE_AFTER = "before_after"
    METRIC_SUMMARY = "metric_summary"
    STRATEGY = "strategy"
    PROCESS = "process"
    TIMELINE = "timeline"
    DIAGRAM = "diagram"
    TEXT_ARGUMENT = "text_argument"
    IMAGE_TEXT_HYBRID = "image_text_hybrid"
    MULTI_IMAGE_GRID = "multi_image_grid"
    COVER_VISUAL = "cover_visual"
    SECTION_VISUAL = "section_visual"
    CONCLUSION = "conclusion"
    UNKNOWN = "unknown"


class FunctionalSlideClassification(DomainModel):
    slide_id: str = Field(min_length=1)
    slide_index: int = Field(ge=0)
    functional_type: FunctionalSlideType = FunctionalSlideType.UNKNOWN
    content_type: ArchitecturalContentType = ArchitecturalContentType.UNKNOWN
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list)
    needs_review: bool = False


class ReferenceSlideCluster(DomainModel):
    id: str = Field(default_factory=lambda: str(uuid4()), min_length=1)
    functional_type: FunctionalSlideType = FunctionalSlideType.CONTENT
    content_type: ArchitecturalContentType = ArchitecturalContentType.UNKNOWN
    slide_ids: list[str] = Field(default_factory=list)
    representative_slide_id: str = ""
    visual_similarity: float = Field(default=0.0, ge=0.0, le=1.0)
    structural_similarity: float = Field(default=0.0, ge=0.0, le=1.0)
    semantic_similarity: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    selection_rationale: list[str] = Field(default_factory=list)
    needs_review: bool = False


class RepresentativeSlideScore(DomainModel):
    slide_id: str = Field(min_length=1)
    cluster_id: str = Field(min_length=1)
    cluster_centrality: float = 0.0
    structural_completeness: float = 0.0
    editability: float = 0.0
    visual_clarity: float = 0.0
    reuse_potential: float = 0.0
    anomaly_penalty: float = 0.0
    excessive_complexity_penalty: float = 0.0
    total_score: float = 0.0
    rationale: list[str] = Field(default_factory=list)


class InductionReviewOverride(DomainModel):
    """Human correction fields — not a numeric score."""

    slide_id: str = Field(min_length=1)
    functional_type: FunctionalSlideType | None = None
    content_type: ArchitecturalContentType | None = None
    cluster_id: str | None = None
    is_representative: bool | None = None
    notes: str = ""


class TemplateInductionStatus(StrEnum):
    DRAFT = "draft"
    REVIEW = "review"
    READY = "ready"


class TemplateInductionResult(IdentifiedModel, TimestampedModel):
    """File-oriented induction package for Phase 0–3 acceptance."""

    name: str = Field(min_length=1)
    workspace_relative: str = ""
    source_filename: str = ""
    slide_count: int = Field(default=0, ge=0)
    status: TemplateInductionStatus = TemplateInductionStatus.DRAFT
    classifications: list[FunctionalSlideClassification] = Field(default_factory=list)
    clusters: list[ReferenceSlideCluster] = Field(default_factory=list)
    representative_scores: list[RepresentativeSlideScore] = Field(default_factory=list)
    overrides: list[InductionReviewOverride] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    low_confidence_slide_ids: list[str] = Field(default_factory=list)

    def classification_for(self, slide_id: str) -> FunctionalSlideClassification | None:
        for item in self.classifications:
            if item.slide_id == slide_id:
                return item
        return None


class OutlineTemplateCompatibility(DomainModel):
    """Placeholder for Phase 5 — kept so Outline can already reference the shape."""

    slide_id: str = Field(min_length=1)
    outline_purpose: str = ""
    compatible_layout_ids: list[str] = Field(default_factory=list)
    preferred_layout_id: str | None = None
    compatibility_score: float = Field(default=0.0, ge=0.0, le=1.0)
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    fallback_mode: Literal[
        "template_editing",
        "free_composition",
        "manual_required",
    ] = "free_composition"
