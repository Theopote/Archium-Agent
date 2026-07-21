"""Architectural content schema — what a template page must communicate."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal
from uuid import uuid4

from pydantic import Field, model_validator

from archium.domain._base import DomainModel, TimestampedModel
from archium.domain.visual.template_induction import (
    ArchitecturalContentType,
    FunctionalSlideType,
    VisualLayoutPattern,
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
    label: str = ""


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


class UsageCondition(DomainModel):
    """When this schema should (or should not) be selected during co-planning."""

    field: Literal[
        "functional_type",
        "content_type",
        "requires_drawing",
        "min_evidence_count",
        "section_category",
    ]
    operator: Literal["eq", "in", "gte", "not_eq"] = "eq"
    value: str | int | list[str] = ""
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
    visual_layout_pattern: VisualLayoutPattern = VisualLayoutPattern.UNKNOWN

    page_purpose: str = Field(min_length=1)
    audience_effect: str = ""
    central_claim_required: bool = True

    # PPTAgent-style communication contract (semantic layer — not geometry).
    reference_paragraphs: list[str] = Field(default_factory=list)
    central_claim: ContentRequirement | None = None
    evidence_items: list[ContentRequirement] = Field(default_factory=list)
    visual_evidence: list[VisualRequirement] = Field(default_factory=list)
    interpretation: ContentRequirement | None = None
    decision_request: ContentRequirement | None = None

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

    usage_conditions: list[UsageCondition] = Field(default_factory=list)

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
        ) or bool(self.visual_evidence)

    @property
    def slide_purpose(self) -> str:
        """Alias for ``page_purpose`` (PPTAgent / task-book vocabulary)."""
        return self.page_purpose

    @slide_purpose.setter
    def slide_purpose(self, value: str) -> None:
        self.page_purpose = value

    def hydrate_semantic_contract(self) -> ArchitecturalContentSchema:
        """Populate semantic fields from flat lists (legacy JSON readers)."""
        if self.central_claim is None:
            for item in self.required_content:
                if item.role == ContentRole.CENTRAL_CLAIM:
                    object.__setattr__(self, "central_claim", item)
                    break
        if not self.evidence_items:
            object.__setattr__(
                self,
                "evidence_items",
                [i for i in self.required_content if i.role == ContentRole.EVIDENCE],
            )
        if not self.visual_evidence:
            evidence_roles = {
                "hero_image",
                "supporting_image",
                "drawing",
                "before_after_pair",
                "multi_image_grid",
            }
            object.__setattr__(
                self,
                "visual_evidence",
                [v for v in self.visual_requirements if v.role in evidence_roles],
            )
        if self.interpretation is None:
            for item in self.required_content:
                if item.role == ContentRole.INTERPRETATION:
                    object.__setattr__(self, "interpretation", item)
                    break
        if self.decision_request is None:
            for item in self.required_content:
                if item.role == ContentRole.DECISION_REQUEST:
                    object.__setattr__(self, "decision_request", item)
                    break
        return self

    def apply_semantic_contract(self) -> ArchitecturalContentSchema:
        """Merge semantic contract into ``required_content`` / ``visual_requirements``."""
        merged_content: list[ContentRequirement] = []
        seen_roles: set[ContentRole] = set()

        def add_unique(item: ContentRequirement | None) -> None:
            if item is None or item.role in seen_roles:
                return
            merged_content.append(item)
            seen_roles.add(item.role)

        add_unique(next((r for r in self.required_content if r.role == ContentRole.TITLE), None))
        add_unique(self.central_claim)
        for item in self.evidence_items:
            add_unique(item)
        add_unique(self.interpretation)
        add_unique(self.decision_request)
        for item in self.required_content:
            if item.role in seen_roles:
                continue
            if item.role in {
                ContentRole.CENTRAL_CLAIM,
                ContentRole.EVIDENCE,
                ContentRole.INTERPRETATION,
                ContentRole.DECISION_REQUEST,
            }:
                continue
            merged_content.append(item)
            seen_roles.add(item.role)

        visual = list(self.visual_requirements)
        visual_roles = {v.role for v in visual}
        for item in self.visual_evidence:
            if item.role not in visual_roles:
                visual.append(item)
                visual_roles.add(item.role)

        object.__setattr__(self, "required_content", merged_content)
        object.__setattr__(self, "visual_requirements", visual)
        self.central_claim_required = self.central_claim is not None and self.central_claim.required
        return self

    @model_validator(mode="after")
    def _default_semantic_hydration(self) -> ArchitecturalContentSchema:
        if (
            self.central_claim is None
            and not self.evidence_items
            and not self.visual_evidence
            and self.required_content
        ):
            return self.hydrate_semantic_contract()
        return self


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
