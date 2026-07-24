"""Validate and convert mission LLM drafts to domain models."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import TypeVar
from uuid import UUID

from archium.domain.enums import (
    AssumptionStatus,
    ConstraintSource,
    InterventionScale,
    KnowledgeGapCategory,
    Priority,
    ProjectDomain,
    QuestionAnswerType,
    ServiceDepth,
    TaskNature,
    UncertaintyLevel,
    VerificationStatus,
)
from archium.domain.fact import ProjectFact
from archium.domain.knowledge_gap import (
    Assumption,
    ClarifyingQuestion,
    DesignQuestion,
    KnowledgeGap,
)
from archium.domain.intent.design_intent import DesignIntent
from archium.domain.project_mission import (
    EvaluationCriterion,
    MissionConstraint,
    ProjectMission,
    Stakeholder,
)
from archium.infrastructure.llm.mission_schemas import (
    MissionConstraintDraft,
    MissionGenerationDraft,
)

PROTECTED_FACT_KEYS = frozenset(
    {
        "site_area",
        "land_area",
        "building_area",
        "gross_floor_area",
        "height",
        "building_height",
        "plot_ratio",
        "far",
        "budget",
        "floors",
        "floor_count",
    }
)

_NUMERIC_CLAIM_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:㎡|m²|平方米|米|m|公顷|ha|万|亿)?",
    re.IGNORECASE,
)

MAX_CLARIFYING_QUESTIONS = 5
MAX_CONCEPT_CLARIFYING_QUESTIONS = 3


@dataclass
class MissionParseResult:
    mission: ProjectMission
    knowledge_gaps: list[KnowledgeGap] = field(default_factory=list)
    assumptions: list[Assumption] = field(default_factory=list)
    clarifying_questions: list[ClarifyingQuestion] = field(default_factory=list)
    design_questions: list[DesignQuestion] = field(default_factory=list)
    validation_warnings: list[str] = field(default_factory=list)


@dataclass
class MissionValidationResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def validate_mission_draft(
    draft: MissionGenerationDraft,
    facts: list[ProjectFact],
    *,
    lightweight_mode: bool = False,
    concept_mode: bool | None = None,
) -> MissionValidationResult:
    """Check draft for fabrication, conflict mishandling, and question limits."""
    if concept_mode is not None:
        lightweight_mode = concept_mode
    result = MissionValidationResult()
    active_facts = [fact for fact in facts if fact.verification_status != VerificationStatus.REJECTED]
    confirmed = {fact.key: fact for fact in active_facts if fact.is_confirmed}
    conflicted_keys = {
        fact.key
        for fact in active_facts
        if fact.verification_status == VerificationStatus.CONFLICTED
    }

    max_questions = (
        MAX_CONCEPT_CLARIFYING_QUESTIONS if lightweight_mode else MAX_CLARIFYING_QUESTIONS
    )
    if len(draft.clarifying_questions) > max_questions:
        result.warnings.append(
            f"clarifying_questions 超过 {max_questions} 个，将截断"
        )

    if lightweight_mode:
        for index, question in enumerate(draft.clarifying_questions):
            if question.blocking:
                result.warnings.append(
                    f"轻量规划模式下 clarifying_questions[{index}] 不应阻塞，将视为非阻塞"
                )

    for key in conflicted_keys:
        if _draft_claims_resolved_conflict(draft, key):
            result.errors.append(f"冲突事实 {key} 不得在未经用户确认的情况下被选定")

    for key, fact in confirmed.items():
        if key in PROTECTED_FACT_KEYS and not _draft_preserves_fact(draft, fact):
            result.warnings.append(f"已确认事实 {fact.label} 未在 known_constraints 中保留，将自动补入")

    for constraint in draft.known_constraints:
        if not _looks_like_metric_constraint(constraint):
            continue
        if not _constraint_supported_by_facts(constraint, active_facts):
            if constraint.verification_status == VerificationStatus.USER_CONFIRMED.value:
                result.errors.append(
                    f"约束「{constraint.name}」标记为已确认但缺少事实账本依据"
                )
            elif _constraint_contains_numeric(constraint):
                result.errors.append(
                    f"约束「{constraint.name}」包含无资料依据的指标数值，不得作为已确认条件"
                )

    return result


def parse_mission_draft(
    draft: MissionGenerationDraft,
    *,
    project_id: UUID,
    facts: list[ProjectFact],
    version: int = 1,
    lightweight_mode: bool = False,
    concept_mode: bool | None = None,
) -> MissionParseResult:
    """Convert LLM draft to domain models with fact-aware sanitization."""
    if concept_mode is not None:
        lightweight_mode = concept_mode
    validation = validate_mission_draft(draft, facts, lightweight_mode=lightweight_mode)
    if not validation.ok:
        raise ValueError("; ".join(validation.errors))

    mission = ProjectMission(
        project_id=project_id,
        title=draft.title,
        task_statement=draft.task_statement,
        task_natures=_parse_enums(draft.task_natures, TaskNature, TaskNature.OTHER),
        domains=_parse_enums(draft.domains, ProjectDomain, ProjectDomain.OTHER),
        intervention_scales=_parse_enums(
            draft.intervention_scales, InterventionScale, InterventionScale.SITE
        ),
        requested_service_depths=_parse_enums(
            draft.requested_service_depths, ServiceDepth, ServiceDepth.TASK_INTERPRETATION
        ),
        project_context=draft.project_context,
        current_situation=draft.current_situation,
        primary_problems=list(draft.primary_problems),
        desired_changes=list(draft.desired_changes),
        in_scope=list(draft.in_scope),
        out_of_scope=list(draft.out_of_scope),
        stakeholders=[Stakeholder.model_validate(item.model_dump()) for item in draft.stakeholders],
        decision_context=draft.decision_context,
        decisions_required=list(draft.decisions_required),
        known_constraints=_sanitize_constraints(draft.known_constraints, facts),
        key_unknowns=list(draft.key_unknowns),
        research_questions=list(draft.research_questions),
        design_questions=list(draft.design_question_summaries),
        evaluation_criteria=[
            EvaluationCriterion.model_validate(item.model_dump())
            for item in draft.evaluation_criteria
        ],
        design_intent=(
            DesignIntent.model_validate(draft.design_intent.model_dump())
            if draft.design_intent is not None
            else None
        ),
        uncertainty_level=_parse_enum(draft.uncertainty_level, UncertaintyLevel, UncertaintyLevel.MEDIUM),
        confidence=draft.confidence,
        version=version,
    )
    _inject_confirmed_facts(mission, facts)

    gaps = [
        KnowledgeGap(
            project_id=project_id,
            mission_id=mission.id,
            category=_parse_enum(item.category, KnowledgeGapCategory, KnowledgeGapCategory.OTHER),
            question=item.question,
            why_it_matters=item.why_it_matters,
            impact_if_unresolved=item.impact_if_unresolved,
            priority=_parse_enum(item.priority, Priority, Priority.MEDIUM),
            blocking=False if concept_mode else item.blocking,
        )
        for item in draft.knowledge_gaps
    ]

    assumptions = [
        Assumption(
            project_id=project_id,
            mission_id=mission.id,
            statement=item.statement,
            reason=item.reason,
            scope_of_use=item.scope_of_use,
            confidence=item.confidence,
            risk_level=item.risk_level,
            requires_confirmation=item.requires_confirmation,
            status=AssumptionStatus.PROPOSED,
        )
        for item in draft.assumptions
    ]

    max_questions = (
        MAX_CONCEPT_CLARIFYING_QUESTIONS if concept_mode else MAX_CLARIFYING_QUESTIONS
    )
    capped_questions = draft.clarifying_questions[:max_questions]
    clarifying = []
    for item in capped_questions:
        gap_id = None
        if item.knowledge_gap_index is not None and 0 <= item.knowledge_gap_index < len(gaps):
            gap_id = gaps[item.knowledge_gap_index].id
        blocking = False if concept_mode else item.blocking
        clarifying.append(
            ClarifyingQuestion(
                project_id=project_id,
                mission_id=mission.id,
                knowledge_gap_id=gap_id,
                question=item.question,
                why_asked=item.why_asked,
                answer_type=_parse_enum(item.answer_type, QuestionAnswerType, QuestionAnswerType.TEXT),
                options=list(item.options),
                priority=_parse_enum(item.priority, Priority, Priority.MEDIUM),
                blocking=blocking,
                can_assume=item.can_assume if not concept_mode else True,
                suggested_assumption=item.suggested_assumption,
            )
        )

    design_questions = [
        DesignQuestion(
            project_id=project_id,
            mission_id=mission.id,
            question=item.question,
            context=item.context,
            related_problem=item.related_problem,
            constraints=list(item.constraints),
            desired_outcome=item.desired_outcome,
            priority=_parse_enum(item.priority, Priority, Priority.MEDIUM),
        )
        for item in draft.design_questions
    ]

    return MissionParseResult(
        mission=mission,
        knowledge_gaps=gaps,
        assumptions=assumptions,
        clarifying_questions=clarifying,
        design_questions=design_questions,
        validation_warnings=list(validation.warnings),
    )


def _parse_enum(value: str, enum_cls: type[_EnumT], fallback: _EnumT) -> _EnumT:
    try:
        return enum_cls(value)
    except ValueError:
        return fallback


def _parse_enums(values: list[str], enum_cls: type[_EnumT], fallback: _EnumT) -> list[_EnumT]:
    parsed = []
    for value in values:
        try:
            parsed.append(enum_cls(value))
        except ValueError:
            parsed.append(fallback)
    return parsed


def _sanitize_constraints(
    constraints: list,
    facts: list[ProjectFact],
) -> list[MissionConstraint]:
    active_keys = {
        fact.key
        for fact in facts
        if fact.verification_status
        not in {VerificationStatus.REJECTED, VerificationStatus.CONFLICTED}
    }
    result: list[MissionConstraint] = []
    for item in constraints:
        constraint = MissionConstraint(
            name=item.name,
            value=item.value,
            source=_parse_enum(item.source, ConstraintSource, ConstraintSource.OTHER),
            verification_status=_parse_enum(
                item.verification_status, VerificationStatus, VerificationStatus.INFERRED
            ),
            evidence_refs=list(item.evidence_refs),
            importance=item.importance,
        )
        if _constraint_contains_unsupported_metric(constraint, facts):
            constraint.verification_status = VerificationStatus.INFERRED
        if constraint.verification_status == VerificationStatus.USER_CONFIRMED and not _has_fact_support(
            constraint, active_keys
        ):
            constraint.verification_status = VerificationStatus.INFERRED
        result.append(constraint)
    return result


def _inject_confirmed_facts(mission: ProjectMission, facts: list[ProjectFact]) -> None:
    existing = {item.name.lower(): item for item in mission.known_constraints}
    for fact in facts:
        if not fact.is_confirmed:
            continue
        label_key = fact.label.lower()
        if label_key in existing or fact.key in existing:
            continue
        mission.known_constraints.append(
            MissionConstraint(
                name=fact.label,
                value=str(fact.value) + (f" {fact.unit}" if fact.unit else ""),
                source=ConstraintSource.DOCUMENT,
                verification_status=VerificationStatus.USER_CONFIRMED,
                importance="high",
            )
        )


def _draft_preserves_fact(draft: MissionGenerationDraft, fact: ProjectFact) -> bool:
    value_text = str(fact.value)
    for constraint in draft.known_constraints:
        if (
            (fact.label in constraint.name or fact.key.replace("_", " ") in constraint.name.lower())
            and value_text in constraint.value
        ):
            return True
    combined = " ".join(
        [
            draft.task_statement,
            draft.project_context,
            draft.current_situation,
            " ".join(draft.key_unknowns),
        ]
    )
    return value_text in combined or fact.label in combined


def _draft_claims_resolved_conflict(draft: MissionGenerationDraft, key: str) -> bool:
    for constraint in draft.known_constraints:
        if (
            key.replace("_", " ") in constraint.name.lower() or key in constraint.name.lower()
        ) and constraint.verification_status in {
            VerificationStatus.USER_CONFIRMED.value,
            VerificationStatus.EXTRACTED.value,
        }:
            return True
    return False


def _constraint_contains_unsupported_metric(
    constraint: MissionConstraint,
    facts: list[ProjectFact],
) -> bool:
    if not _looks_like_metric_constraint(constraint):
        return False
    return not _constraint_supported_by_facts(constraint, facts)


def _looks_like_metric_constraint(
    constraint: MissionConstraint | MissionConstraintDraft,
) -> bool:
    if _constraint_contains_numeric(constraint):
        name_lower = constraint.name.lower()
        if any(token in name_lower for token in ("面积", "高度", "预算", "用地", "层数", "容积")):
            return True
        if any(key in name_lower for key in ("area", "height", "budget", "floor")):
            return True
    return False


def _constraint_contains_numeric(
    constraint: MissionConstraint | MissionConstraintDraft,
) -> bool:
    return _NUMERIC_CLAIM_RE.search(constraint.value) is not None


def _constraint_supported_by_facts(
    constraint: MissionConstraint | MissionConstraintDraft, facts: list[ProjectFact]
) -> bool:
    for fact in facts:
        if fact.verification_status in {
            VerificationStatus.USER_CONFIRMED,
            VerificationStatus.EXTRACTED,
        } and (str(fact.value) in constraint.value or fact.label in constraint.name):
            return True
    return False


def _has_fact_support(constraint: MissionConstraint, active_keys: set[str]) -> bool:
    name_lower = constraint.name.lower()
    return any(key.replace("_", " ") in name_lower or key in name_lower for key in active_keys)


_EnumT = TypeVar("_EnumT", bound=Enum)
