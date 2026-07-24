"""Project mission — formal understanding of an architectural task."""

from __future__ import annotations

from uuid import UUID, uuid4

from pydantic import Field, field_validator

from archium.domain._base import DomainModel, IdentifiedModel, TimestampedModel, VersionedModel
from archium.domain.architectural_narrative_mode import ArchitecturalNarrativeMode
from archium.domain.intent.design_intent import DesignIntent
from archium.domain.enums import (
    ApprovalStatus,
    ConstraintSource,
    InterventionScale,
    ProjectDomain,
    ServiceDepth,
    TaskNature,
    UncertaintyLevel,
    VerificationStatus,
)

MISSION_LOGICAL_KEY = "project-mission"


class Stakeholder(DomainModel):
    """A person or group with interest in project outcomes."""

    name: str = Field(min_length=1, max_length=200)
    role: str = Field(min_length=1, max_length=200)
    concerns: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    influence_level: str | None = None


class MissionConstraint(DomainModel):
    """A known constraint affecting the mission scope or approach."""

    name: str = Field(min_length=1, max_length=200)
    value: str = Field(min_length=1)
    source: ConstraintSource = ConstraintSource.OTHER
    verification_status: VerificationStatus = VerificationStatus.EXTRACTED
    evidence_refs: list[str] = Field(default_factory=list)
    importance: str = "medium"


class EvaluationCriterion(DomainModel):
    """Criterion for evaluating mission outcomes."""

    name: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1)
    weight: float | None = Field(default=None, ge=0.0, le=1.0)
    measurement_method: str | None = None
    source: str = "mission"


class ProjectMission(IdentifiedModel, VersionedModel, TimestampedModel):
    """Structured understanding of what the current architectural task is."""

    project_id: UUID
    lineage_id: UUID = Field(default_factory=uuid4)
    logical_key: str = Field(default=MISSION_LOGICAL_KEY, max_length=200)
    title: str = Field(min_length=1, max_length=500)
    task_statement: str = Field(min_length=1)
    task_natures: list[TaskNature] = Field(default_factory=list)
    domains: list[ProjectDomain] = Field(default_factory=list)
    intervention_scales: list[InterventionScale] = Field(default_factory=list)
    requested_service_depths: list[ServiceDepth] = Field(default_factory=list)
    project_context: str = ""
    current_situation: str = ""
    primary_problems: list[str] = Field(default_factory=list)
    desired_changes: list[str] = Field(default_factory=list)
    in_scope: list[str] = Field(default_factory=list)
    out_of_scope: list[str] = Field(default_factory=list)
    stakeholders: list[Stakeholder] = Field(default_factory=list)
    decision_context: str = ""
    decisions_required: list[str] = Field(default_factory=list)
    narrative_mode: ArchitecturalNarrativeMode | None = None
    design_intent: DesignIntent | None = None
    approval_hash: str | None = Field(default=None, max_length=64)
    known_constraints: list[MissionConstraint] = Field(default_factory=list)
    key_unknowns: list[str] = Field(default_factory=list)
    research_questions: list[str] = Field(default_factory=list)
    design_questions: list[str] = Field(default_factory=list)
    evaluation_criteria: list[EvaluationCriterion] = Field(default_factory=list)
    recommended_workstream_ids: list[UUID] = Field(default_factory=list)
    recommended_deliverable_ids: list[str] = Field(default_factory=list)
    uncertainty_level: UncertaintyLevel = UncertaintyLevel.MEDIUM
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    approval_status: ApprovalStatus = ApprovalStatus.DRAFT

    @field_validator("task_natures", "domains", "intervention_scales", "requested_service_depths")
    @classmethod
    def _dedupe_enums(cls, values: list) -> list:
        if not values:
            return values
        seen: set = set()
        deduped = []
        for item in values:
            if item not in seen:
                seen.add(item)
                deduped.append(item)
        return deduped

    def approve(self) -> None:
        self.approval_status = ApprovalStatus.APPROVED
        self.touch()

    def invalidate_approval(self) -> None:
        """Make downstream approvals stale after approved mission content changes."""
        self.approval_status = ApprovalStatus.DRAFT
        self.approval_hash = None
        self.touch()

    def reject(self) -> None:
        self.approval_status = ApprovalStatus.REJECTED
        self.touch()

    def touch(self) -> None:
        TimestampedModel.touch(self)
