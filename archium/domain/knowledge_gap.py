"""Knowledge gaps, assumptions, and clarifying questions for project missions."""

from __future__ import annotations

from uuid import UUID

from pydantic import Field, model_validator

from archium.domain._base import IdentifiedModel, TimestampedModel
from archium.domain.enums import (
    ApprovalStatus,
    AssumptionStatus,
    KnowledgeGapCategory,
    KnowledgeGapStatus,
    Priority,
    QuestionAnswerType,
    QuestionStatus,
    ResolutionMethod,
)

AnswerValue = str | list[str] | bool | float | None


class KnowledgeGap(IdentifiedModel, TimestampedModel):
    """An identified gap in project knowledge that affects planning."""

    project_id: UUID
    mission_id: UUID
    category: KnowledgeGapCategory = KnowledgeGapCategory.OTHER
    question: str = Field(min_length=1)
    why_it_matters: str = Field(min_length=1)
    impact_if_unresolved: str = ""
    resolution_methods: list[ResolutionMethod] = Field(default_factory=list)
    suggested_owner: str | None = None
    priority: Priority = Priority.MEDIUM
    blocking: bool = False
    status: KnowledgeGapStatus = KnowledgeGapStatus.OPEN
    resolution: str | None = None

    def mark_assumed(self, assumption_text: str) -> None:
        self.status = KnowledgeGapStatus.ASSUMED
        self.resolution = assumption_text
        self.touch()

    def mark_answered(self, answer: str) -> None:
        self.status = KnowledgeGapStatus.ANSWERED
        self.resolution = answer
        self.touch()

    def defer(self) -> None:
        self.status = KnowledgeGapStatus.DEFERRED
        self.touch()

    def touch(self) -> None:
        TimestampedModel.touch(self)


class Assumption(IdentifiedModel, TimestampedModel):
    """A formal assumption used when information is incomplete."""

    project_id: UUID
    mission_id: UUID
    statement: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    scope_of_use: str = ""
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    risk_level: str = "medium"
    requires_confirmation: bool = True
    status: AssumptionStatus = AssumptionStatus.PROPOSED
    related_gap_ids: list[UUID] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)

    def accept(self) -> None:
        self.status = AssumptionStatus.ACCEPTED
        self.touch()

    def reject(self) -> None:
        self.status = AssumptionStatus.REJECTED
        self.touch()

    def confirm(self) -> None:
        self.status = AssumptionStatus.CONFIRMED
        self.touch()

    def touch(self) -> None:
        TimestampedModel.touch(self)


class ClarifyingQuestion(IdentifiedModel, TimestampedModel):
    """A question posed to the user to resolve mission uncertainty."""

    project_id: UUID
    mission_id: UUID
    knowledge_gap_id: UUID | None = None
    question: str = Field(min_length=1)
    why_asked: str = Field(min_length=1)
    answer_type: QuestionAnswerType = QuestionAnswerType.TEXT
    options: list[str] = Field(default_factory=list)
    priority: Priority = Priority.MEDIUM
    blocking: bool = False
    can_assume: bool = True
    suggested_assumption: str = ""
    answer: AnswerValue = None
    answer_source: str | None = None
    status: QuestionStatus = QuestionStatus.OPEN

    @model_validator(mode="after")
    def _choice_requires_options(self) -> ClarifyingQuestion:
        if (
            self.answer_type in (QuestionAnswerType.SINGLE_CHOICE, QuestionAnswerType.MULTI_CHOICE)
            and not self.options
        ):
            raise ValueError("choice questions require at least one option")
        return self

    def answer_with(self, value: AnswerValue, *, source: str = "user") -> None:
        self.answer = value
        self.answer_source = source
        self.status = QuestionStatus.ANSWERED
        self.touch()

    def assume(self, assumption: str | None = None) -> None:
        self.answer = assumption or self.suggested_assumption or None
        self.answer_source = "assumption"
        self.status = QuestionStatus.ASSUMED
        self.touch()

    def defer(self) -> None:
        self.status = QuestionStatus.DEFERRED
        self.touch()

    def mark_not_applicable(self) -> None:
        self.status = QuestionStatus.NOT_APPLICABLE
        self.touch()

    def touch(self) -> None:
        TimestampedModel.touch(self)


class DesignQuestion(IdentifiedModel, TimestampedModel):
    """A design proposition framing conditions, contradictions, and goals."""

    project_id: UUID
    mission_id: UUID
    question: str = Field(min_length=1)
    context: str = ""
    related_problem: str = ""
    constraints: list[str] = Field(default_factory=list)
    desired_outcome: str = ""
    priority: Priority = Priority.MEDIUM
    status: ApprovalStatus = ApprovalStatus.DRAFT

    def approve(self) -> None:
        self.status = ApprovalStatus.APPROVED
        self.touch()

    def touch(self) -> None:
        TimestampedModel.touch(self)
