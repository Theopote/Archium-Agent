"""Real architectural project acceptance domain models."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field, field_validator, model_validator

from archium.domain._base import DomainModel
from archium.domain.enums import PipelineRole
from archium.domain.pipeline_role_mapping import (
    default_stage_pipeline_roles,
    pipeline_roles_for_e2e_stages,
)

REAL_PROJECT_MIN_SLIDES = 15
REAL_PROJECT_MAX_SLIDES = 30
REAL_PROJECT_MIN_ASSETS = 10


class RealProjectScenario(StrEnum):
    """Five required real-project acceptance scenarios."""

    NEW_BUILDING = "new_building"
    EXISTING_RENOVATION = "existing_renovation"
    HOSPITAL_SCHOOL_ANALYSIS = "hospital_school_analysis"
    GOVERNMENT_CLIENT_DECISION = "government_client_decision"
    INTERNAL_DESIGN_REVIEW = "internal_design_review"
    CULTURAL_VILLAGE = "cultural_village"


class HumanMetricsSource(StrEnum):
    """Provenance of optional human rehearsal fields on acceptance records."""

    NONE = "none"
    LAYOUT_QA_DERIVED = "layout_qa_derived"
    STUDIO_MANUAL = "studio_manual"


class RealProjectAcceptanceMetrics(DomainModel):
    """Automated and manual metrics recorded for one acceptance run."""

    first_generation_seconds: float = Field(ge=0.0)
    generation_succeeded: bool = False
    slide_count: int = Field(ge=0)
    asset_count: int = Field(ge=0)
    layout_plan_count: int = Field(ge=0)
    critical_layout_page_count: int = Field(ge=0)
    error_layout_page_count: int = Field(ge=0)
    drawing_crop_issue_count: int = Field(ge=0)
    export_acceptable: bool = False
    real_asset_utilization_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    # Manual fields — filled during live rehearsal / usability sessions.
    major_edit_page_ratio: float | None = Field(default=None, ge=0.0, le=1.0)
    minor_edit_page_ratio: float | None = Field(default=None, ge=0.0, le=1.0)
    exported_page_ratio: float | None = Field(default=None, ge=0.0, le=1.0)
    average_human_visual_score: float | None = Field(default=None, ge=1.0, le=5.0)
    user_edit_minutes: float | None = Field(default=None, ge=0.0)
    # Phase 7 extended fields — manual session / final sign-off.
    input_document_count: int | None = Field(default=None, ge=0)
    modified_page_count: int | None = Field(default=None, ge=0)
    unmodified_page_ratio: float | None = Field(default=None, ge=0.0, le=1.0)
    fact_error_count: int | None = Field(default=None, ge=0)
    citation_error_count: int | None = Field(default=None, ge=0)
    image_usage_error_count: int | None = Field(default=None, ge=0)
    deliverable_ready: bool | None = None
    top_dissatisfactions: list[str] = Field(default_factory=list)
    top_satisfactions: list[str] = Field(default_factory=list)

    @field_validator("top_dissatisfactions", "top_satisfactions")
    @classmethod
    def _limit_top_five(cls, value: list[str]) -> list[str]:
        return value[:5]

    def meets_automated_scope(self) -> bool:
        """Return True when slide/asset counts match sprint minimum scope."""
        return (
            REAL_PROJECT_MIN_SLIDES <= self.slide_count <= REAL_PROJECT_MAX_SLIDES
            and self.asset_count >= REAL_PROJECT_MIN_ASSETS
        )

    def has_manual_human_metrics(self) -> bool:
        return self.average_human_visual_score is not None


class RealProjectAcceptanceRecord(DomainModel):
    """Persisted acceptance record for one real-project scenario."""

    project_id: str = Field(min_length=1)
    scenario: RealProjectScenario
    title: str = Field(min_length=1)
    run_at: datetime
    metrics: RealProjectAcceptanceMetrics
    human_metrics_source: HumanMetricsSource = HumanMetricsSource.NONE
    human_rehearsal_passed: bool = False
    notes: str = ""


class Phase7ProjectProfile(DomainModel):
    """On-disk profile for Phase 7 real-project acceptance folders."""

    id: str = Field(min_length=1)
    scenario: RealProjectScenario
    name: str = Field(min_length=1)
    project_type: str = Field(min_length=1)
    workflow_phase: str = Field(default="phase_7_acceptance", min_length=1)
    target_slide_count: int = Field(ge=1)
    required_pipeline_stages: list[str] = Field(min_length=1)
    stage_pipeline_roles: dict[str, PipelineRole] = Field(default_factory=dict)
    required_pipeline_roles: list[PipelineRole] = Field(default_factory=list)
    description: str = ""

    @model_validator(mode="after")
    def _normalize_pipeline_roles(self) -> Phase7ProjectProfile:
        stages = [s.strip().lower() for s in self.required_pipeline_stages if s.strip()]
        roles_map = dict(self.stage_pipeline_roles) if self.stage_pipeline_roles else {}
        if not roles_map:
            roles_map = default_stage_pipeline_roles(stages)
        else:
            roles_map = {k.strip().lower(): v for k, v in roles_map.items()}
        unique_roles = pipeline_roles_for_e2e_stages(stages)
        if not unique_roles:
            unique_roles = list(dict.fromkeys(roles_map.values()))
        object.__setattr__(self, "required_pipeline_stages", stages)
        object.__setattr__(self, "stage_pipeline_roles", roles_map)
        object.__setattr__(self, "required_pipeline_roles", unique_roles)
        return self


class Phase7HumanReviewBundle(DomainModel):
    """Deck-level manual review export for Phase 7 folders."""

    project_id: str = Field(min_length=1)
    source: str = Field(default="manual")
    reviews: list[dict[str, object]] = Field(default_factory=list)
    reviewer: str = ""
    reviewed_at: datetime | None = None
    notes: str = ""
