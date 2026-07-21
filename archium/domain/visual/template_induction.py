"""Template induction classification and clustering models (Phase 0–3)."""

from __future__ import annotations

from datetime import datetime
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
    PUBLISHED = "published"


class Phase35HumanSignoff(DomainModel):
    """Human exception review sign-off for real reference deck validation."""

    status: Literal["PASS", "PASS_WITH_WARNINGS", "NEEDS_REVIEW", "BLOCKED"]
    reviewer: str = ""
    notes: str = ""
    run_reference: str = ""
    signed_at: datetime | None = None

    @property
    def allows_formal_publish(self) -> bool:
        return self.status in {"PASS", "PASS_WITH_WARNINGS"}


class TemplateInductionResult(IdentifiedModel, TimestampedModel):
    """File-oriented induction package for Phase 0–4 acceptance."""

    name: str = Field(min_length=1)
    workspace_relative: str = ""
    source_filename: str = ""
    slide_count: int = Field(default=0, ge=0)
    status: TemplateInductionStatus = TemplateInductionStatus.DRAFT
    classifications: list[FunctionalSlideClassification] = Field(default_factory=list)
    clusters: list[ReferenceSlideCluster] = Field(default_factory=list)
    representative_scores: list[RepresentativeSlideScore] = Field(default_factory=list)
    overrides: list[InductionReviewOverride] = Field(default_factory=list)
    # Phase 4 — content schemas keyed by cluster representatives.
    content_schemas: list[dict[str, object]] = Field(default_factory=list)
    publish_report: dict[str, object] | None = None
    warnings: list[str] = Field(default_factory=list)
    low_confidence_slide_ids: list[str] = Field(default_factory=list)
    phase35_signoff: Phase35HumanSignoff | None = None
    architectural_template_id: str = ""

    def classification_for(self, slide_id: str) -> FunctionalSlideClassification | None:
        for item in self.classifications:
            if item.slide_id == slide_id:
                return item
        return None


class OutlineTemplateCompatibility(DomainModel):
    """One planned content page mapped to a template schema/layout (Phase 5)."""

    # Stable id for this planned page slot (not a project SlideSpec id yet).
    slide_id: str = Field(min_length=1)
    section_id: str = ""
    section_title: str = ""
    outline_purpose: str = ""
    planned_page_index: int = Field(default=0, ge=0)
    page_role: Literal["primary", "overflow", "section_opener"] = "primary"

    inferred_functional_type: FunctionalSlideType = FunctionalSlideType.CONTENT
    inferred_content_type: ArchitecturalContentType = ArchitecturalContentType.UNKNOWN

    schema_id: str | None = None
    representative_slide_id: str | None = None
    compatible_layout_ids: list[str] = Field(default_factory=list)
    preferred_layout_id: str | None = None

    template_affinity: float = Field(default=0.0, ge=0.0, le=1.0)
    compatibility_score: float = Field(default=0.0, ge=0.0, le=1.0)
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    fallback_mode: Literal[
        "template_editing",
        "free_composition",
        "manual_required",
    ] = "free_composition"
    # Phase 6: populated when template_editing route executes scene generation.
    edit_scene_status: Literal["pending", "generated", "skipped", "failed"] = "pending"
    edit_scene_relative_path: str = ""


class TemplateEditingPageResult(DomainModel):
    """One co-plan page executed through reference-slide editing."""

    slide_id: str = Field(min_length=1)
    section_id: str = ""
    schema_id: str | None = None
    representative_slide_id: str | None = None
    layout_id: str | None = None
    status: Literal["generated", "skipped", "failed"]
    edit_scene_relative_path: str = ""
    node_count: int = Field(default=0, ge=0)
    stripped_text_count: int = Field(default=0, ge=0)
    stripped_asset_count: int = Field(default=0, ge=0)
    warnings: list[str] = Field(default_factory=list)
    error: str = ""


class OutlineTemplateEditingBatch(DomainModel):
    """Batch result for co-plan ``template_editing`` scene generation."""

    co_plan_id: str = ""
    outline_id: str = ""
    induction_id: str = ""
    template_id: str = ""
    page_results: list[TemplateEditingPageResult] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @property
    def generated_count(self) -> int:
        return sum(1 for page in self.page_results if page.status == "generated")

    @property
    def skipped_count(self) -> int:
        return sum(1 for page in self.page_results if page.status == "skipped")

    @property
    def failed_count(self) -> int:
        return sum(1 for page in self.page_results if page.status == "failed")


class SchemaAffinityScore(DomainModel):
    """How well one induced schema fits an outline section intent."""

    schema_id: str = Field(min_length=1)
    section_id: str = Field(min_length=1)
    affinity: float = Field(default=0.0, ge=0.0, le=1.0)
    reasons: list[str] = Field(default_factory=list)


class OutlineTemplateCoPlan(IdentifiedModel, TimestampedModel):
    """Phase 5 artifact: outline sections ↔ template schemas with fallback routing."""

    outline_id: str = ""
    outline_title: str = ""
    induction_id: str = ""
    template_id: str = ""
    page_plans: list[OutlineTemplateCompatibility] = Field(default_factory=list)
    schema_affinities: list[SchemaAffinityScore] = Field(default_factory=list)
    # Template/schema pages that never received an outline assignment (exposed for review).
    unmatched_schema_ids: list[str] = Field(default_factory=list)
    unmatched_layout_ids: list[str] = Field(default_factory=list)
    free_composition_page_ids: list[str] = Field(default_factory=list)
    template_editing_page_ids: list[str] = Field(default_factory=list)
    manual_required_page_ids: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    planning_method: str = "rule_driven_outline_template_v1"

    @property
    def planned_page_count(self) -> int:
        return len(self.page_plans)
