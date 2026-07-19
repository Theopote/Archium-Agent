"""Real architectural project acceptance domain models."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field

from archium.domain._base import DomainModel

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
