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


class DesignProcessFocus(StrEnum):
    """Fine-grained Design process focus (stored on ProcessPointer.focus)."""

    IDLE = "idle"
    EXPLORING = "exploring"
    COMPARING_DIRECTIONS = "comparing_directions"
    DIRECTION_SELECTED = "direction_selected"
    VISUAL_DRAFT = "visual_draft"
    VISUAL_FAILED = "visual_failed"
    VISUAL_READY = "visual_ready"
    MISSION_CLARIFYING = "mission_clarifying"
    MISSION_APPROVED = "mission_approved"
    COMMITTED = "committed"


_DESIGN_FOCUS_ZH = {
    DesignProcessFocus.IDLE: "未开始",
    DesignProcessFocus.EXPLORING: "概念探索",
    DesignProcessFocus.COMPARING_DIRECTIONS: "比较方向",
    DesignProcessFocus.DIRECTION_SELECTED: "方向已选",
    DesignProcessFocus.VISUAL_DRAFT: "视觉简报草稿",
    DesignProcessFocus.VISUAL_FAILED: "出图受阻",
    DesignProcessFocus.VISUAL_READY: "视觉简报就绪",
    DesignProcessFocus.MISSION_CLARIFYING: "Mission 澄清",
    DesignProcessFocus.MISSION_APPROVED: "Mission 已批",
    DesignProcessFocus.COMMITTED: "已提交 Mission",
}


class ProcessPointer(DomainModel):
    """Handle into process-owned state (ids + phase only)."""

    kind: ProjectProcessKind
    phase: ProjectProcessPhase = ProjectProcessPhase.IDLE
    focus: str = Field(default="", max_length=40)
    active_id: UUID | None = None
    secondary_id: UUID | None = None
    label: str = Field(default="", max_length=200)
    detail: str = Field(default="", max_length=300)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def design_focus(self) -> DesignProcessFocus | None:
        if self.kind != ProjectProcessKind.DESIGN:
            return None
        raw = (self.focus or "").strip()
        if not raw:
            return None
        try:
            return DesignProcessFocus(raw)
        except ValueError:
            return None


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
        design_bit = _phase_zh(self.design.phase)
        focus = self.design.design_focus()
        if focus is not None and focus != DesignProcessFocus.IDLE:
            design_bit = f"{design_bit}/{_DESIGN_FOCUS_ZH.get(focus, focus.value)}"
        parts = [
            f"研究:{_phase_zh(self.research.phase)}",
            f"设计:{design_bit}",
            f"汇报:{_phase_zh(self.presentation.phase)}",
        ]
        return " · ".join(parts)


def design_focus_label(focus: DesignProcessFocus | str | None) -> str:
    if focus is None:
        return ""
    if isinstance(focus, str):
        try:
            focus = DesignProcessFocus(focus)
        except ValueError:
            return focus
    return _DESIGN_FOCUS_ZH.get(focus, focus.value)


def _phase_zh(phase: ProjectProcessPhase) -> str:
    return {
        ProjectProcessPhase.IDLE: "未开始",
        ProjectProcessPhase.ACTIVE: "进行中",
        ProjectProcessPhase.BLOCKED: "受阻",
        ProjectProcessPhase.READY: "可推进",
        ProjectProcessPhase.COMPLETE: "已完成",
    }.get(phase, phase.value)
