"""Input models for Brief and Storyline human review."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from archium.domain.presentation import Presentation, PresentationBrief, Storyline
from archium.domain.workflow import WorkflowRun


@dataclass(frozen=True)
class BriefUpdate:
    title: str
    audience: str
    purpose: str
    core_message: str
    duration_minutes: int = 20
    target_slide_count: int = 20
    tone: str = "professional"
    language: str = "zh-CN"
    required_sections: list[str] = field(default_factory=list)
    decisions_required: list[str] = field(default_factory=list)
    audience_concerns: list[str] = field(default_factory=list)
    excluded_topics: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ChapterUpdate:
    id: str
    title: str
    purpose: str
    key_message: str
    order: int
    estimated_slide_count: int = 1


@dataclass(frozen=True)
class StorylineUpdate:
    thesis: str
    narrative_pattern: str = "problem_solution"
    chapters: list[ChapterUpdate] = field(default_factory=list)


@dataclass(frozen=True)
class PresentationReviewContext:
    presentation: Presentation
    brief: PresentationBrief | None
    storyline: Storyline | None
    workflow_run: WorkflowRun | None = None

    @property
    def review_gate(self) -> str | None:
        if self.workflow_run is None:
            return None
        return self.workflow_run.state.get("review_gate")

    @property
    def awaiting_review(self) -> bool:
        if self.workflow_run is None:
            return False
        from archium.domain.enums import WorkflowStatus

        return self.workflow_run.status == WorkflowStatus.AWAITING_REVIEW


def parse_multiline_items(text: str) -> list[str]:
    value = text.strip()
    if not value:
        return []
    lines = [part.strip() for part in value.splitlines() if part.strip()]
    if len(lines) > 1:
        return lines
    single = lines[0] if lines else value
    for separator in ("、", "，", ","):
        if separator in single:
            return [part.strip() for part in single.split(separator) if part.strip()]
    return [single]
