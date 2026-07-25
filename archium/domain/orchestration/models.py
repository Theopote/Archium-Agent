"""Product orchestration stages — Planning-seat durable stage runs (not Agents)."""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import Field

from archium.domain._base import DomainModel, IdentifiedModel, TimestampedModel


class OrchestrationStage(StrEnum):
    """Ordered product stages the orchestrator can advance through."""

    EXPLORE = "explore"
    RESEARCH = "research"
    MATERIALS = "materials"
    MISSION_PLANNING = "mission_planning"
    WORKSTREAM_EXECUTION = "workstream_execution"
    PRESENTATION = "presentation"
    VISUAL = "visual"
    DELIVER = "deliver"


class OrchestrationStageStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    AWAITING_USER = "awaiting_user"
    AWAITING_REVIEW = "awaiting_review"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


class OrchestrationPlanSource(StrEnum):
    NBA = "nba"
    RECOMMENDED_WORKFLOW = "recommended_workflow"
    MANUAL = "manual"
    CONTEXT_REPLAN = "context_replan"


class OrchestrationStageSpec(DomainModel):
    """One stage slot in an orchestration plan."""

    stage: OrchestrationStage
    status: OrchestrationStageStatus = OrchestrationStageStatus.PENDING
    workflow_run_id: UUID | None = None
    page_key: str | None = None
    skip_reason: str = ""
    label: str = ""


class OrchestrationPlan(IdentifiedModel, TimestampedModel):
    """Ordered stages derived from ProjectContext / RecommendedWorkflow."""

    project_id: UUID
    source: OrchestrationPlanSource = OrchestrationPlanSource.RECOMMENDED_WORKFLOW
    stages: list[OrchestrationStageSpec] = Field(default_factory=list)
    active_index: int = 0

    def active_stage(self) -> OrchestrationStageSpec | None:
        if not self.stages:
            return None
        if self.active_index < 0 or self.active_index >= len(self.stages):
            return None
        return self.stages[self.active_index]

    def mark_active(
        self,
        status: OrchestrationStageStatus,
        *,
        workflow_run_id: UUID | None = None,
        skip_reason: str = "",
    ) -> OrchestrationStageSpec | None:
        stage = self.active_stage()
        if stage is None:
            return None
        stage.status = status
        if workflow_run_id is not None:
            stage.workflow_run_id = workflow_run_id
        if skip_reason:
            stage.skip_reason = skip_reason
        self.touch()
        return stage

    def advance_index(self) -> OrchestrationStageSpec | None:
        if self.active_index + 1 >= len(self.stages):
            return None
        self.active_index += 1
        self.touch()
        return self.active_stage()

    def is_complete(self) -> bool:
        if not self.stages:
            return True
        return all(
            spec.status
            in {
                OrchestrationStageStatus.COMPLETED,
                OrchestrationStageStatus.SKIPPED,
            }
            for spec in self.stages
        )


class WorkstreamNodeSpec(DomainModel):
    """One executable node compiled from a selected Workstream."""

    workstream_id: UUID = Field(default_factory=uuid4)
    workstream_type: str = ""
    title: str = ""
    depends_on: list[UUID] = Field(default_factory=list)
    handler_key: str = "skip"
