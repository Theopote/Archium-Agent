"""Bounded autonomous research run — artifact for Research role loop."""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import Field

from archium.domain._base import DomainModel, TimestampedModel, utc_now


class ResearchRunStopReason(StrEnum):
    """Why the bounded research loop ended."""

    TOPICS_EXHAUSTED = "topics_exhausted"
    MAX_STEPS = "max_steps"
    RESEARCH_NEED_MET = "research_need_met"
    EMPTY_FINDINGS = "empty_findings"
    NO_TOPICS = "no_topics"
    BATCH = "batch"  # legacy single-shot path


class ResearchStepStatus(StrEnum):
    OK = "ok"
    EMPTY = "empty"
    FAILED = "failed"


class ResearchStep(DomainModel):
    """One bounded-loop iteration: select topic(s) → search → synthesize → write."""

    index: int = 0
    topics: list[str] = Field(default_factory=list)
    status: ResearchStepStatus = ResearchStepStatus.OK
    finding_count: int = 0
    search_hit_count: int = 0
    research_need_before: float | None = None
    research_need_after: float | None = None
    warning: str = ""
    knowledge_item_ids: list[UUID] = Field(default_factory=list)


class ResearchRun(TimestampedModel):
    """In-memory / return artifact for one autonomous research invocation.

    Not a new Agent — consumed by ``AutonomousResearchService`` and NBA Learn.
    Persistence of findings remains on ``ProjectKnowledgeItem``.
    """

    id: UUID = Field(default_factory=uuid4)
    project_id: UUID
    mission_id: UUID | None = None
    planned_topics: list[str] = Field(default_factory=list)
    completed_topics: list[str] = Field(default_factory=list)
    steps: list[ResearchStep] = Field(default_factory=list)
    stop_reason: ResearchRunStopReason = ResearchRunStopReason.BATCH
    research_need_before: float | None = None
    research_need_after: float | None = None
    max_steps: int = 1
    loop_enabled: bool = False

    @property
    def step_count(self) -> int:
        return len(self.steps)

    @property
    def finding_count(self) -> int:
        return sum(step.finding_count for step in self.steps)

    def summary_line(self) -> str:
        need = ""
        if self.research_need_before is not None and self.research_need_after is not None:
            need = (
                f" · research_need "
                f"{int(round(self.research_need_before * 100))}%→"
                f"{int(round(self.research_need_after * 100))}%"
            )
        return (
            f"研究环 {self.step_count}/{self.max_steps} 步"
            f" · 产出 {self.finding_count} 条"
            f" · 停止 {self.stop_reason.value}"
            f"{need}"
        )

    def touch_completed(self) -> None:
        self.updated_at = utc_now()
