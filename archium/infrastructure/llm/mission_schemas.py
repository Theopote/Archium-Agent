"""Structured LLM output schemas for project mission generation."""

from __future__ import annotations

from pydantic import BaseModel, Field


class StakeholderDraft(BaseModel):
    name: str
    role: str
    concerns: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    influence_level: str | None = None


class MissionConstraintDraft(BaseModel):
    name: str
    value: str
    source: str = "other"
    verification_status: str = "extracted"
    evidence_refs: list[str] = Field(default_factory=list)
    importance: str = "medium"


class EvaluationCriterionDraft(BaseModel):
    name: str
    description: str
    weight: float | None = Field(default=None, ge=0.0, le=1.0)
    measurement_method: str | None = None
    source: str = "mission"


class KnowledgeGapDraft(BaseModel):
    category: str = "other"
    question: str
    why_it_matters: str
    impact_if_unresolved: str = ""
    resolution_methods: list[str] = Field(default_factory=list)
    priority: str = "medium"
    blocking: bool = False


class AssumptionDraft(BaseModel):
    statement: str
    reason: str
    scope_of_use: str = ""
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    risk_level: str = "medium"
    requires_confirmation: bool = True


class ClarifyingQuestionDraft(BaseModel):
    question: str
    why_asked: str
    answer_type: str = "text"
    options: list[str] = Field(default_factory=list)
    priority: str = "medium"
    blocking: bool = False
    can_assume: bool = True
    suggested_assumption: str = ""
    knowledge_gap_index: int | None = None


class DesignQuestionDraft(BaseModel):
    question: str
    context: str = ""
    related_problem: str = ""
    constraints: list[str] = Field(default_factory=list)
    desired_outcome: str = ""
    priority: str = "medium"


class MissionGenerationDraft(BaseModel):
    """LLM output for task understanding and initial planning artifacts."""

    title: str
    task_statement: str
    task_natures: list[str] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)
    intervention_scales: list[str] = Field(default_factory=list)
    requested_service_depths: list[str] = Field(default_factory=list)
    project_context: str = ""
    current_situation: str = ""
    primary_problems: list[str] = Field(default_factory=list)
    desired_changes: list[str] = Field(default_factory=list)
    in_scope: list[str] = Field(default_factory=list)
    out_of_scope: list[str] = Field(default_factory=list)
    stakeholders: list[StakeholderDraft] = Field(default_factory=list)
    decision_context: str = ""
    decisions_required: list[str] = Field(default_factory=list)
    known_constraints: list[MissionConstraintDraft] = Field(default_factory=list)
    key_unknowns: list[str] = Field(default_factory=list)
    research_questions: list[str] = Field(default_factory=list)
    design_question_summaries: list[str] = Field(default_factory=list)
    evaluation_criteria: list[EvaluationCriterionDraft] = Field(default_factory=list)
    uncertainty_level: str = "medium"
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    knowledge_gaps: list[KnowledgeGapDraft] = Field(default_factory=list)
    assumptions: list[AssumptionDraft] = Field(default_factory=list)
    clarifying_questions: list[ClarifyingQuestionDraft] = Field(default_factory=list)
    design_questions: list[DesignQuestionDraft] = Field(default_factory=list)
