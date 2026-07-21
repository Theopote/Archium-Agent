"""Architectural content schema — what a template page must communicate."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal
from uuid import uuid4

from pydantic import Field

from archium.domain._base import DomainModel, TimestampedModel
from archium.domain.visual.template_induction import (
    ArchitecturalContentType,
    FunctionalSlideType,
)


class ContentRole(StrEnum):
    TITLE = "title"
    CENTRAL_CLAIM = "central_claim"
    LEAD_STATEMENT = "lead_statement"
    BODY = "body"
    EVIDENCE = "evidence"
    METRIC = "metric"
    CAPTION = "caption"
    INTERPRETATION = "interpretation"
    DECISION_REQUEST = "decision_request"
    SOURCE = "source"


class ContentRequirement(DomainModel):
    role: ContentRole
    required: bool = True
    min_count: int = Field(default=1, ge=0)
    max_count: int = Field(default=1, ge=0)
    min_length: int = Field(default=0, ge=0)
    max_length: int = Field(default=500, ge=0)
    semantic_description: str = ""


class VisualRequirement(DomainModel):
    role: Literal[
        "hero_image",
        "supporting_image",
        "drawing",
        "chart",
        "table",
        "decoration",
        "before_after_pair",
        "multi_image_grid",
    ]
    required: bool = True
    min_count: int = Field(default=1, ge=0)
    max_count: int = Field(default=1, ge=0)
    fit_mode: Literal["contain", "cover", "fit"] = "contain"
    description: str = ""


class EvidenceRequirement(DomainModel):
    evidence_type: Literal[
        "project_photo",
        "drawing",
        "metric",
        "document_quote",
        "historic_archive",
        "reference_case",
        "public_research",
    ]
    required: bool = True
    min_count: int = Field(default=1, ge=0)
    max_count: int = Field(default=4, ge=0)
    must_be_observable_in_asset: bool = False
    description: str = ""


class ArchitecturalContentSchema(TimestampedModel):
    """Communication contract for one induced template page type."""

    id: str = Field(default_factory=lambda: str(uuid4()), min_length=1)
    name: str = Field(min_length=1, max_length=200)
    cluster_id: str = ""
    representative_slide_id: str = ""
    cluster_member_count: int = Field(default=1, ge=1)
    functional_type: FunctionalSlideType = FunctionalSlideType.CONTENT
    content_type: ArchitecturalContentType = ArchitecturalContentType.UNKNOWN

    page_purpose: str = Field(min_length=1)
    audience_effect: str = ""
    central_claim_required: bool = True

    required_content: list[ContentRequirement] = Field(default_factory=list)
    optional_content: list[ContentRequirement] = Field(default_factory=list)
    visual_requirements: list[VisualRequirement] = Field(default_factory=list)
    evidence_requirements: list[EvidenceRequirement] = Field(default_factory=list)

    allowed_asset_origins: list[str] = Field(
        default_factory=lambda: ["project_upload", "public_research"]
    )
    forbidden_asset_origins: list[str] = Field(
        default_factory=lambda: ["reference_template", "ai_generated"]
    )

    min_text_length: int = Field(default=0, ge=0)
    max_text_length: int = Field(default=2000, ge=0)
    min_asset_count: int = Field(default=0, ge=0)
    max_asset_count: int = Field(default=8, ge=0)

    supports_drawing: bool = False
    allowed_drawing_types: list[str] = Field(default_factory=list)

    citation_required: bool = False
    caption_required: bool = False
    metric_unit_required: bool = False

    architectural_constraints: list[str] = Field(default_factory=list)
    extraction_evidence: list[str] = Field(default_factory=list)
    cluster_stats: dict[str, float | int] = Field(default_factory=dict)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    needs_review: bool = False
    human_corrected: bool = False
    test_fill_passed: bool | None = None

    def required_roles(self) -> set[str]:
        return {item.role.value for item in self.required_content if item.required}

    def has_drawing_slot(self) -> bool:
        return self.supports_drawing or any(
            v.role == "drawing" for v in self.visual_requirements
        )

    def has_image_slot(self) -> bool:
        return any(
            v.role in {"hero_image", "supporting_image", "before_after_pair", "multi_image_grid"}
            for v in self.visual_requirements
        )


class SchemaPublishBlocker(DomainModel):
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    cluster_id: str = ""
    slide_id: str = ""
    schema_id: str = ""


class SchemaTestFillResult(DomainModel):
    """Structural test fill against representative slide — not full RenderScene."""

    schema_id: str = Field(min_length=1)
    representative_slide_id: str = ""
    required_slots_filled: bool = False
    text_overflow: bool = False
    missing_assets: bool = False
    drawing_policy_passed: bool = True
    reference_leakage: bool = False
    render_valid: bool = False
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class SchemaPublishReport(DomainModel):
    """Publish gate result — status vocabulary without numeric scores."""

    status: Literal["PASS", "PASS_WITH_WARNINGS", "NEEDS_REVIEW", "BLOCKED"] = "BLOCKED"
    blockers: list[SchemaPublishBlocker] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    schema_ids: list[str] = Field(default_factory=list)
    test_fill_results: list[SchemaTestFillResult] = Field(default_factory=list)

    @property
    def can_publish(self) -> bool:
        return self.status in {"PASS", "PASS_WITH_WARNINGS"}

    @property
    def can_formally_publish(self) -> bool:
        """Formal template publication — warnings must be cleared first."""
        return self.status == "PASS"


class SchemaReviewOverride(DomainModel):
    """Human correction of schema fields — not a 1–5 score."""

    schema_id: str = Field(min_length=1)
    page_purpose: str | None = None
    central_claim_required: bool | None = None
    supports_drawing: bool | None = None
    citation_required: bool | None = None
    caption_required: bool | None = None
    allowed_asset_origins: list[str] | None = None
    forbidden_asset_origins: list[str] | None = None
    notes: str = ""


def new_schema_id() -> str:
    return str(uuid4())
