"""Research questions — problem objects that drive research (not case keywords)."""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import Field

from archium.domain._base import DomainModel


class ResearchQuestionCategory(StrEnum):
    SOCIAL = "social"
    CULTURAL = "cultural"
    HISTORICAL = "historical"
    ENVIRONMENTAL = "environmental"
    BEHAVIORAL = "behavioral"
    ECONOMIC = "economic"
    TECHNICAL = "technical"
    ARCHITECTURAL = "architectural"


class ResearchQuestionStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    ANSWERED = "answered"
    DEFERRED = "deferred"


class ResearchQuestionDepth(StrEnum):
    SCAN = "scan"  # quick background
    STANDARD = "standard"
    DEEP = "deep"


class ResearchQuestion(DomainModel):
    """One design-relevant research problem (not a search keyword dump)."""

    question: str = Field(min_length=1)
    category: ResearchQuestionCategory = ResearchQuestionCategory.ARCHITECTURAL
    related_intent: str = ""
    priority: float = Field(default=0.5, ge=0.0, le=1.0)
    required_depth: ResearchQuestionDepth = ResearchQuestionDepth.STANDARD
    status: ResearchQuestionStatus = ResearchQuestionStatus.OPEN
    source: str = ""
    rationale: str = ""
    mission_id: UUID | None = None
    project_id: UUID | None = None

    def as_search_topic(self) -> str:
        """Topic string for web search / research loop (keeps problem framing)."""
        return self.question.strip()

    def to_prompt_line(self) -> str:
        cat = self.category.value
        return f"[{cat}] {self.question.strip()}"
