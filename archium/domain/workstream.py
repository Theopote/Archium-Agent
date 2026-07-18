"""Planning workstreams — composable research and analysis capabilities."""

from __future__ import annotations

from uuid import UUID, uuid4

from pydantic import Field, model_validator

from archium.domain._base import IdentifiedModel, TimestampedModel, VersionedModel
from archium.domain.enums import EffortLevel, Priority, WorkstreamStatus, WorkstreamType


def detect_workstream_dependency_cycles(workstreams: list[Workstream]) -> list[UUID]:
    """Return IDs participating in a dependency cycle, or empty if acyclic."""
    by_id = {ws.id: ws for ws in workstreams}
    visited: set[UUID] = set()
    stack: set[UUID] = set()
    cycle_nodes: list[UUID] = []

    def visit(node_id: UUID) -> bool:
        if node_id in stack:
            cycle_nodes.append(node_id)
            return True
        if node_id in visited:
            return False
        visited.add(node_id)
        stack.add(node_id)
        ws = by_id.get(node_id)
        if ws is not None:
            for dep_id in ws.dependencies:
                if dep_id not in by_id:
                    continue
                if visit(dep_id):
                    cycle_nodes.append(node_id)
                    return True
        stack.remove(node_id)
        return False

    for ws_id in by_id:
        visit(ws_id)
    return list(dict.fromkeys(reversed(cycle_nodes)))


class Workstream(IdentifiedModel, VersionedModel, TimestampedModel):
    """A recommended or selected research/analysis work path for a mission."""

    project_id: UUID
    mission_id: UUID
    lineage_id: UUID = Field(default_factory=uuid4)
    title: str = Field(min_length=1, max_length=500)
    workstream_type: WorkstreamType = WorkstreamType.OTHER
    objective: str = Field(min_length=1)
    questions: list[str] = Field(default_factory=list)
    inputs_required: list[str] = Field(default_factory=list)
    activities: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    dependencies: list[UUID] = Field(default_factory=list)
    blocking_gaps: list[UUID] = Field(default_factory=list)
    priority: Priority = Priority.MEDIUM
    effort_level: EffortLevel = EffortLevel.MEDIUM
    recommended: bool = True
    recommendation_reason: str = ""
    selected: bool = False
    status: WorkstreamStatus = WorkstreamStatus.PROPOSED

    def select(self) -> None:
        self.selected = True
        self.status = WorkstreamStatus.SELECTED
        self.touch()

    def deselect(self) -> None:
        self.selected = False
        if self.status == WorkstreamStatus.SELECTED:
            self.status = WorkstreamStatus.PROPOSED
        self.touch()

    def touch(self) -> None:
        TimestampedModel.touch(self)


class WorkstreamPlan(IdentifiedModel, VersionedModel, TimestampedModel):
    """Versioned collection of workstreams for a mission."""

    project_id: UUID
    mission_id: UUID
    lineage_id: UUID = Field(default_factory=uuid4)
    workstreams: list[Workstream] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_no_dependency_cycles(self) -> WorkstreamPlan:
        cycles = detect_workstream_dependency_cycles(self.workstreams)
        if cycles:
            raise ValueError("workstream dependencies contain a cycle")
        return self

    def touch(self) -> None:
        TimestampedModel.touch(self)
