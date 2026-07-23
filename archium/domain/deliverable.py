"""Deliverable planning — planned outputs for a mission."""

from __future__ import annotations

from uuid import UUID, uuid4

from pydantic import Field

from archium.domain._base import DomainModel, IdentifiedModel, TimestampedModel, VersionedModel
from archium.domain.enums import ApprovalStatus, DeliverableType

DELIVERABLE_PLAN_LOGICAL_KEY = "deliverable-plan"


class PlannedDeliverable(DomainModel):
    """A single planned output artifact."""

    id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=500)
    deliverable_type: DeliverableType = DeliverableType.OTHER
    purpose: str = Field(min_length=1)
    audience: str = ""
    content_scope: list[str] = Field(default_factory=list)
    source_workstream_ids: list[UUID] = Field(default_factory=list)
    required: bool = False
    selected: bool = False
    format: str = "markdown"
    expected_length: str | None = None
    notes: str | None = None

    def select(self) -> None:
        self.selected = True

    def deselect(self) -> None:
        self.selected = False


class DeliverablePlan(IdentifiedModel, VersionedModel, TimestampedModel):
    """Versioned plan of deliverables for a mission."""

    project_id: UUID
    mission_id: UUID
    lineage_id: UUID = Field(default_factory=uuid4)
    logical_key: str = Field(default=DELIVERABLE_PLAN_LOGICAL_KEY, max_length=200)
    deliverables: list[PlannedDeliverable] = Field(default_factory=list)
    approval_status: ApprovalStatus = ApprovalStatus.DRAFT

    def selected_deliverables(self) -> list[PlannedDeliverable]:
        return [item for item in self.deliverables if item.selected]

    def approve(self) -> None:
        self.approval_status = ApprovalStatus.APPROVED
        self.touch()

    def invalidate_approval(self) -> None:
        """Clear approval after plan content/selection changes."""
        self.approval_status = ApprovalStatus.DRAFT
        self.touch()

    def reject(self) -> None:
        self.approval_status = ApprovalStatus.REJECTED
        self.touch()

    def touch(self) -> None:
        TimestampedModel.touch(self)
