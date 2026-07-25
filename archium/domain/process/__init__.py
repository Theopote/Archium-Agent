"""Project process board — sibling of ProjectContext, not absorbed into it.

ProjectContext answers cognitive questions (known / unknown / stage / NBA).
Process pointers hold *which process is active* and phase — never design
bodies, slide trees, or render scenes.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from pydantic import Field

from archium.domain._base import DomainModel


class ProjectProcessKind(StrEnum):
    RESEARCH = "research"
    DESIGN = "design"
    PRESENTATION = "presentation"


class ProjectProcessPhase(StrEnum):
    IDLE = "idle"
    ACTIVE = "active"
    BLOCKED = "blocked"
    READY = "ready"
    COMPLETE = "complete"


class ProcessPointer(DomainModel):
    """Handle into process-owned state (ids + phase only)."""

    kind: ProjectProcessKind
    phase: ProjectProcessPhase = ProjectProcessPhase.IDLE
    active_id: UUID | None = None
    label: str = Field(default="", max_length=200)
    detail: str = Field(default="", max_length=300)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ProjectProcessBoard(DomainModel):
    """Derived board of Research / Design / Presentation process phases.

    Lives beside ProjectContext under Project. Do not merge into ProjectContext.
    """

    research: ProcessPointer = Field(
        default_factory=lambda: ProcessPointer(kind=ProjectProcessKind.RESEARCH)
    )
    design: ProcessPointer = Field(
        default_factory=lambda: ProcessPointer(kind=ProjectProcessKind.DESIGN)
    )
    presentation: ProcessPointer = Field(
        default_factory=lambda: ProcessPointer(kind=ProjectProcessKind.PRESENTATION)
    )

    def summary_line(self) -> str:
        parts = [
            f"研究:{_phase_zh(self.research.phase)}",
            f"设计:{_phase_zh(self.design.phase)}",
            f"汇报:{_phase_zh(self.presentation.phase)}",
        ]
        return " · ".join(parts)


def _phase_zh(phase: ProjectProcessPhase) -> str:
    return {
        ProjectProcessPhase.IDLE: "未开始",
        ProjectProcessPhase.ACTIVE: "进行中",
        ProjectProcessPhase.BLOCKED: "受阻",
        ProjectProcessPhase.READY: "可推进",
        ProjectProcessPhase.COMPLETE: "已完成",
    }.get(phase, phase.value)
