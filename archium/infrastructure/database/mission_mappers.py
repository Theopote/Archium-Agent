"""Mappers for project mission and adaptive planning persistence."""

from __future__ import annotations

from typing import cast
from uuid import UUID

from archium.domain.architectural_narrative_mode import ArchitecturalNarrativeMode
from archium.domain.deliverable import (
    DELIVERABLE_PLAN_LOGICAL_KEY,
    DeliverablePlan,
    PlannedDeliverable,
)
from archium.domain.enums import (
    ApprovalStatus,
    AssumptionStatus,
    EffortLevel,
    InterventionScale,
    KnowledgeGapCategory,
    KnowledgeGapStatus,
    Priority,
    ProjectDomain,
    QuestionAnswerType,
    QuestionStatus,
    ResolutionMethod,
    ServiceDepth,
    TaskNature,
    UncertaintyLevel,
    WorkstreamStatus,
    WorkstreamType,
)
from archium.domain.knowledge_gap import (
    AnswerValue,
    Assumption,
    ClarifyingQuestion,
    DesignQuestion,
    KnowledgeGap,
)
from archium.domain.project_mission import (
    MISSION_LOGICAL_KEY,
    EvaluationCriterion,
    MissionConstraint,
    ProjectMission,
    Stakeholder,
)
from archium.domain.workstream import Workstream
from archium.infrastructure.database.models import (
    ClarifyingQuestionORM,
    DeliverablePlanORM,
    DesignQuestionORM,
    KnowledgeGapORM,
    ProjectAssumptionORM,
    ProjectMissionORM,
    WorkstreamORM,
)


def _uuid_list_to_json(values: list[UUID]) -> list[str]:
    return [str(value) for value in values]


def _uuid_list_from_json(values: list[str]) -> list[UUID]:
    return [UUID(value) for value in values]


# ── ProjectMission ─────────────────────────────────────────────


def project_mission_to_domain(orm: ProjectMissionORM) -> ProjectMission:
    return ProjectMission(
        id=orm.id,
        project_id=orm.project_id,
        lineage_id=orm.lineage_id or orm.id,
        logical_key=orm.logical_key or MISSION_LOGICAL_KEY,
        title=orm.title,
        task_statement=orm.task_statement,
        task_natures=[TaskNature(value) for value in orm.task_natures_json],
        domains=[ProjectDomain(value) for value in orm.domains_json],
        intervention_scales=[InterventionScale(value) for value in orm.intervention_scales_json],
        requested_service_depths=[
            ServiceDepth(value) for value in orm.requested_service_depths_json
        ],
        project_context=orm.project_context,
        current_situation=orm.current_situation,
        primary_problems=list(orm.primary_problems_json),
        desired_changes=list(orm.desired_changes_json),
        in_scope=list(orm.in_scope_json),
        out_of_scope=list(orm.out_of_scope_json),
        stakeholders=[Stakeholder.model_validate(item) for item in orm.stakeholders_json],
        decision_context=orm.decision_context,
        decisions_required=list(orm.decisions_required_json),
        narrative_mode=(
            ArchitecturalNarrativeMode(orm.narrative_mode) if orm.narrative_mode else None
        ),
        approval_hash=orm.approval_hash,
        known_constraints=[
            MissionConstraint.model_validate(item) for item in orm.known_constraints_json
        ],
        key_unknowns=list(orm.key_unknowns_json),
        research_questions=list(orm.research_questions_json),
        design_questions=list(orm.design_question_summaries_json),
        evaluation_criteria=[
            EvaluationCriterion.model_validate(item) for item in orm.evaluation_criteria_json
        ],
        recommended_workstream_ids=_uuid_list_from_json(list(orm.recommended_workstream_ids_json)),
        recommended_deliverable_ids=list(orm.recommended_deliverable_ids_json),
        uncertainty_level=UncertaintyLevel(orm.uncertainty_level),
        confidence=orm.confidence,
        approval_status=ApprovalStatus(orm.approval_status),
        version=orm.version,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


def project_mission_to_orm(
    domain: ProjectMission,
    orm: ProjectMissionORM | None = None,
) -> ProjectMissionORM:
    target = orm or ProjectMissionORM(id=domain.id)
    target.project_id = domain.project_id
    target.lineage_id = domain.lineage_id
    target.logical_key = domain.logical_key
    target.title = domain.title
    target.task_statement = domain.task_statement
    target.task_natures_json = [item.value for item in domain.task_natures]
    target.domains_json = [item.value for item in domain.domains]
    target.intervention_scales_json = [item.value for item in domain.intervention_scales]
    target.requested_service_depths_json = [item.value for item in domain.requested_service_depths]
    target.project_context = domain.project_context
    target.current_situation = domain.current_situation
    target.primary_problems_json = list(domain.primary_problems)
    target.desired_changes_json = list(domain.desired_changes)
    target.in_scope_json = list(domain.in_scope)
    target.out_of_scope_json = list(domain.out_of_scope)
    target.stakeholders_json = [item.model_dump(mode="json") for item in domain.stakeholders]
    target.decision_context = domain.decision_context
    target.decisions_required_json = list(domain.decisions_required)
    target.narrative_mode = domain.narrative_mode.value if domain.narrative_mode else None
    target.approval_hash = domain.approval_hash
    target.known_constraints_json = [
        item.model_dump(mode="json") for item in domain.known_constraints
    ]
    target.key_unknowns_json = list(domain.key_unknowns)
    target.research_questions_json = list(domain.research_questions)
    target.design_question_summaries_json = list(domain.design_questions)
    target.evaluation_criteria_json = [
        item.model_dump(mode="json") for item in domain.evaluation_criteria
    ]
    target.recommended_workstream_ids_json = _uuid_list_to_json(domain.recommended_workstream_ids)
    target.recommended_deliverable_ids_json = list(domain.recommended_deliverable_ids)
    target.uncertainty_level = domain.uncertainty_level.value
    target.confidence = domain.confidence
    target.approval_status = domain.approval_status.value
    target.version = domain.version
    target.created_at = domain.created_at
    target.updated_at = domain.updated_at
    return target


# ── KnowledgeGap ───────────────────────────────────────────────


def knowledge_gap_to_domain(orm: KnowledgeGapORM) -> KnowledgeGap:
    return KnowledgeGap(
        id=orm.id,
        project_id=orm.project_id,
        mission_id=orm.mission_id,
        category=KnowledgeGapCategory(orm.category),
        question=orm.question,
        why_it_matters=orm.why_it_matters,
        impact_if_unresolved=orm.impact_if_unresolved,
        resolution_methods=[ResolutionMethod(value) for value in orm.resolution_methods_json],
        suggested_owner=orm.suggested_owner,
        priority=Priority(orm.priority),
        blocking=orm.blocking,
        status=KnowledgeGapStatus(orm.status),
        resolution=orm.resolution,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


def knowledge_gap_to_orm(
    domain: KnowledgeGap,
    orm: KnowledgeGapORM | None = None,
) -> KnowledgeGapORM:
    target = orm or KnowledgeGapORM(id=domain.id)
    target.project_id = domain.project_id
    target.mission_id = domain.mission_id
    target.category = domain.category.value
    target.question = domain.question
    target.why_it_matters = domain.why_it_matters
    target.impact_if_unresolved = domain.impact_if_unresolved
    target.resolution_methods_json = [item.value for item in domain.resolution_methods]
    target.suggested_owner = domain.suggested_owner
    target.priority = domain.priority.value
    target.blocking = domain.blocking
    target.status = domain.status.value
    target.resolution = domain.resolution
    target.created_at = domain.created_at
    target.updated_at = domain.updated_at
    return target


# ── Assumption ─────────────────────────────────────────────────


def assumption_to_domain(orm: ProjectAssumptionORM) -> Assumption:
    return Assumption(
        id=orm.id,
        project_id=orm.project_id,
        mission_id=orm.mission_id,
        statement=orm.statement,
        reason=orm.reason,
        scope_of_use=orm.scope_of_use,
        confidence=orm.confidence,
        risk_level=orm.risk_level,
        requires_confirmation=orm.requires_confirmation,
        status=AssumptionStatus(orm.status),
        related_gap_ids=_uuid_list_from_json(list(orm.related_gap_ids_json)),
        evidence_refs=list(orm.evidence_refs_json),
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


def assumption_to_orm(
    domain: Assumption,
    orm: ProjectAssumptionORM | None = None,
) -> ProjectAssumptionORM:
    target = orm or ProjectAssumptionORM(id=domain.id)
    target.project_id = domain.project_id
    target.mission_id = domain.mission_id
    target.statement = domain.statement
    target.reason = domain.reason
    target.scope_of_use = domain.scope_of_use
    target.confidence = domain.confidence
    target.risk_level = domain.risk_level
    target.requires_confirmation = domain.requires_confirmation
    target.status = domain.status.value
    target.related_gap_ids_json = _uuid_list_to_json(domain.related_gap_ids)
    target.evidence_refs_json = list(domain.evidence_refs)
    target.created_at = domain.created_at
    target.updated_at = domain.updated_at
    return target


# ── ClarifyingQuestion ─────────────────────────────────────────


def clarifying_question_to_domain(orm: ClarifyingQuestionORM) -> ClarifyingQuestion:
    return ClarifyingQuestion(
        id=orm.id,
        project_id=orm.project_id,
        mission_id=orm.mission_id,
        knowledge_gap_id=orm.knowledge_gap_id,
        question=orm.question,
        why_asked=orm.why_asked,
        answer_type=QuestionAnswerType(orm.answer_type),
        options=list(orm.options_json),
        priority=Priority(orm.priority),
        blocking=orm.blocking,
        can_assume=orm.can_assume,
        suggested_assumption=orm.suggested_assumption,
        answer=cast(AnswerValue, orm.answer_json),
        answer_source=orm.answer_source,
        status=QuestionStatus(orm.status),
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


def clarifying_question_to_orm(
    domain: ClarifyingQuestion,
    orm: ClarifyingQuestionORM | None = None,
) -> ClarifyingQuestionORM:
    target = orm or ClarifyingQuestionORM(id=domain.id)
    target.project_id = domain.project_id
    target.mission_id = domain.mission_id
    target.knowledge_gap_id = domain.knowledge_gap_id
    target.question = domain.question
    target.why_asked = domain.why_asked
    target.answer_type = domain.answer_type.value
    target.options_json = list(domain.options)
    target.priority = domain.priority.value
    target.blocking = domain.blocking
    target.can_assume = domain.can_assume
    target.suggested_assumption = domain.suggested_assumption
    target.answer_json = domain.answer
    target.answer_source = domain.answer_source
    target.status = domain.status.value
    target.created_at = domain.created_at
    target.updated_at = domain.updated_at
    return target


# ── DesignQuestion ─────────────────────────────────────────────


def design_question_to_domain(orm: DesignQuestionORM) -> DesignQuestion:
    return DesignQuestion(
        id=orm.id,
        project_id=orm.project_id,
        mission_id=orm.mission_id,
        question=orm.question,
        context=orm.context,
        related_problem=orm.related_problem,
        constraints=list(orm.constraints_json),
        desired_outcome=orm.desired_outcome,
        priority=Priority(orm.priority),
        status=ApprovalStatus(orm.status),
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


def design_question_to_orm(
    domain: DesignQuestion,
    orm: DesignQuestionORM | None = None,
) -> DesignQuestionORM:
    target = orm or DesignQuestionORM(id=domain.id)
    target.project_id = domain.project_id
    target.mission_id = domain.mission_id
    target.question = domain.question
    target.context = domain.context
    target.related_problem = domain.related_problem
    target.constraints_json = list(domain.constraints)
    target.desired_outcome = domain.desired_outcome
    target.priority = domain.priority.value
    target.status = domain.status.value
    target.created_at = domain.created_at
    target.updated_at = domain.updated_at
    return target


# ── Workstream ─────────────────────────────────────────────────


def workstream_to_domain(orm: WorkstreamORM) -> Workstream:
    return Workstream(
        id=orm.id,
        project_id=orm.project_id,
        mission_id=orm.mission_id,
        lineage_id=orm.lineage_id,
        title=orm.title,
        workstream_type=WorkstreamType(orm.workstream_type),
        objective=orm.objective,
        questions=list(orm.questions_json),
        inputs_required=list(orm.inputs_required_json),
        activities=list(orm.activities_json),
        outputs=list(orm.outputs_json),
        dependencies=_uuid_list_from_json(list(orm.dependencies_json)),
        blocking_gaps=_uuid_list_from_json(list(orm.blocking_gaps_json)),
        priority=Priority(orm.priority),
        effort_level=EffortLevel(orm.effort_level),
        recommended=orm.recommended,
        recommendation_reason=getattr(orm, "recommendation_reason", "") or "",
        selected=orm.selected,
        status=WorkstreamStatus(orm.status),
        version=orm.version,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


def workstream_to_orm(domain: Workstream, orm: WorkstreamORM | None = None) -> WorkstreamORM:
    target = orm or WorkstreamORM(id=domain.id)
    target.project_id = domain.project_id
    target.mission_id = domain.mission_id
    target.lineage_id = domain.lineage_id
    target.title = domain.title
    target.workstream_type = domain.workstream_type.value
    target.objective = domain.objective
    target.questions_json = list(domain.questions)
    target.inputs_required_json = list(domain.inputs_required)
    target.activities_json = list(domain.activities)
    target.outputs_json = list(domain.outputs)
    target.dependencies_json = _uuid_list_to_json(domain.dependencies)
    target.blocking_gaps_json = _uuid_list_to_json(domain.blocking_gaps)
    target.priority = domain.priority.value
    target.effort_level = domain.effort_level.value
    target.recommended = domain.recommended
    target.recommendation_reason = domain.recommendation_reason
    target.selected = domain.selected
    target.status = domain.status.value
    target.version = domain.version
    target.created_at = domain.created_at
    target.updated_at = domain.updated_at
    return target


# ── DeliverablePlan ──────────────────────────────────────────────


def deliverable_plan_to_domain(orm: DeliverablePlanORM) -> DeliverablePlan:
    return DeliverablePlan(
        id=orm.id,
        project_id=orm.project_id,
        mission_id=orm.mission_id,
        lineage_id=orm.lineage_id or orm.id,
        logical_key=orm.logical_key or DELIVERABLE_PLAN_LOGICAL_KEY,
        deliverables=[PlannedDeliverable.model_validate(item) for item in orm.deliverables_json],
        approval_status=ApprovalStatus(orm.approval_status),
        version=orm.version,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


def deliverable_plan_to_orm(
    domain: DeliverablePlan,
    orm: DeliverablePlanORM | None = None,
) -> DeliverablePlanORM:
    target = orm or DeliverablePlanORM(id=domain.id)
    target.project_id = domain.project_id
    target.mission_id = domain.mission_id
    target.lineage_id = domain.lineage_id
    target.logical_key = domain.logical_key
    target.deliverables_json = [item.model_dump(mode="json") for item in domain.deliverables]
    target.approval_status = domain.approval_status.value
    target.version = domain.version
    target.created_at = domain.created_at
    target.updated_at = domain.updated_at
    return target
