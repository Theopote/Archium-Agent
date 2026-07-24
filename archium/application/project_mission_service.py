"""Project mission generation and revision service."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from uuid import UUID

from pydantic import Field
from sqlalchemy.orm import Session

from archium.application._helpers import build_project_context, to_json
from archium.application.fact_ledger_service import FactLedgerService
from archium.application.mission_history_service import MissionHistoryService
from archium.application.mission_lineage import apply_mission_lineage
from archium.application.mission_parser import (
    parse_mission_draft,
    validate_mission_draft,
)
from archium.config.settings import Settings, get_settings
from archium.domain._base import DomainModel
from archium.domain.architectural_narrative_mode import ArchitecturalNarrativeMode
from archium.domain.enums import (
    ApprovalStatus,
    InterventionScale,
    ProjectDomain,
    ProjectOriginMode,
    RevisionSource,
    ServiceDepth,
    TaskNature,
    UncertaintyLevel,
)
from archium.domain.intent.design_intent import DesignIntent
from archium.domain.knowledge_gap import (
    Assumption,
    ClarifyingQuestion,
    DesignQuestion,
    KnowledgeGap,
)
from archium.domain.project import Project
from archium.domain.project_mission import (
    EvaluationCriterion,
    MissionConstraint,
    ProjectMission,
    Stakeholder,
)
from archium.exceptions import WorkflowError
from archium.infrastructure.database.mission_repositories import MissionRepository
from archium.infrastructure.database.repositories import ProjectRepository
from archium.infrastructure.llm.base import LLMProvider, LLMRequest
from archium.infrastructure.llm.mission_schemas import MissionGenerationDraft
from archium.prompts.project_mission import (
    MISSION_SYSTEM_PROMPT,
    build_mission_regeneration_prompt,
    build_mission_user_prompt,
)


class MissionPatch(DomainModel):
    """Partial update payload for user-edited mission fields."""

    title: str | None = None
    task_statement: str | None = None
    project_context: str | None = None
    current_situation: str | None = None
    primary_problems: list[str] | None = None
    desired_changes: list[str] | None = None
    in_scope: list[str] | None = None
    out_of_scope: list[str] | None = None
    decision_context: str | None = None
    decisions_required: list[str] | None = None
    key_unknowns: list[str] | None = None
    research_questions: list[str] | None = None
    design_questions: list[str] | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    task_natures: list[TaskNature] | None = None
    domains: list[ProjectDomain] | None = None
    intervention_scales: list[InterventionScale] | None = None
    requested_service_depths: list[ServiceDepth] | None = None
    stakeholders: list[Stakeholder] | None = None
    known_constraints: list[MissionConstraint] | None = None
    evaluation_criteria: list[EvaluationCriterion] | None = None
    uncertainty_level: UncertaintyLevel | None = None
    narrative_mode: ArchitecturalNarrativeMode | None = None
    design_intent: DesignIntent | None = None


@dataclass
class MissionGenerationResult:
    mission: ProjectMission
    knowledge_gaps: list[KnowledgeGap] = field(default_factory=list)
    assumptions: list[Assumption] = field(default_factory=list)
    clarifying_questions: list[ClarifyingQuestion] = field(default_factory=list)
    design_questions: list[DesignQuestion] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class ProjectMissionService:
    """Generate, revise, and approve project missions from free-form task descriptions."""

    def __init__(
        self,
        session: Session,
        llm: LLMProvider,
        *,
        settings: Settings | None = None,
    ) -> None:
        self._session = session
        self._llm = llm
        self._settings = settings or get_settings()
        self._projects = ProjectRepository(session)
        self._missions = MissionRepository(session)
        self._fact_ledger = FactLedgerService(session, llm=llm, settings=self._settings)
        self._history = MissionHistoryService(session)

    def generate_mission(
        self,
        project_id: UUID,
        user_task_description: str,
        *,
        origin_mode: ProjectOriginMode | None = None,
    ) -> MissionGenerationResult:
        project = self._require_project(project_id)
        if not user_task_description.strip():
            raise WorkflowError("任务描述不能为空")

        resolved_origin = origin_mode or project.origin_mode
        concept_mode = resolved_origin == ProjectOriginMode.CONCEPT_EXPLORATION
        context = self._build_context(project_id, user_task_description)
        fact_summary = self._build_fact_summary(project_id)
        from archium.prompts.project_mission import (
            build_concept_mission_addendum,
            build_mission_user_prompt,
        )

        user_prompt = build_mission_user_prompt(
            user_task_description=user_task_description,
            project_context=context,
            fact_ledger_summary=fact_summary,
            project_name=project.name,
            project_type=project.project_type.value,
            concept_mode=concept_mode,
        )
        if concept_mode:
            user_prompt += build_concept_mission_addendum()

        draft = self._llm.generate_structured(
            LLMRequest(
                system_prompt=MISSION_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                temperature=0.3,
                json_mode=True,
            ),
            MissionGenerationDraft,
        )
        return self._persist_generation(
            project_id,
            draft,
            concept_mode=concept_mode,
        )

    def regenerate_mission(
        self,
        mission_id: UUID,
        user_feedback: str,
    ) -> MissionGenerationResult:
        previous = self._require_mission(mission_id)
        if not user_feedback.strip():
            raise WorkflowError("修订反馈不能为空")

        context = self._build_context(previous.project_id, previous.task_statement)
        fact_summary = self._build_fact_summary(previous.project_id)
        draft = self._llm.generate_structured(
            LLMRequest(
                system_prompt=MISSION_SYSTEM_PROMPT,
                user_prompt=build_mission_regeneration_prompt(
                    current_mission_json=to_json(previous),
                    user_feedback=user_feedback,
                    project_context=context,
                    fact_ledger_summary=fact_summary,
                ),
                temperature=0.3,
                json_mode=True,
            ),
            MissionGenerationDraft,
        )
        self._clear_mission_artifacts(previous.id)
        self._history.archive_before_regeneration(previous)
        result = self._persist_generation(
            previous.project_id,
            draft,
            previous=previous,
            change_source=RevisionSource.REGENERATION,
        )
        return result

    def update_mission(self, mission_id: UUID, patch: MissionPatch) -> ProjectMission:
        mission = self._require_mission(mission_id)
        payload = mission.model_dump(mode="json")
        payload.update(patch.model_dump(mode="json", exclude_none=True))
        updated = ProjectMission.model_validate(payload)
        if patch.model_dump(exclude_none=True):
            updated.invalidate_approval()
        else:
            updated.touch()
        saved = self._missions.save_mission(updated)
        self._history.record_snapshot(saved, RevisionSource.MANUAL_EDIT)
        return saved

    def approve_mission(
        self,
        mission_id: UUID,
        *,
        user_id: str | None = None,
        note: str | None = None,
    ) -> ProjectMission:
        """Mark the mission approved (domain action only — does not resume workflow)."""
        mission = self._require_mission(mission_id)
        if mission.narrative_mode is None:
            suggestion = suggest_narrative_mode(mission)
            mission.narrative_mode = suggestion.mode
        mission.approve()
        mission.approval_hash = mission_approval_hash(mission)
        saved = self._missions.save_mission(mission)
        history_note = note or "批准任务理解"
        if user_id:
            history_note = f"{history_note} · by {user_id}"
        self._history.record_snapshot(
            saved,
            RevisionSource.APPROVAL,
            note=history_note,
            actor=user_id,
        )
        return saved


    def reject_mission(
        self,
        mission_id: UUID,
        *,
        user_id: str | None = None,
        note: str | None = None,
    ) -> ProjectMission:
        mission = self._require_mission(mission_id)
        mission.reject()
        saved = self._missions.save_mission(mission)
        history_note = note or "驳回任务理解"
        if user_id:
            history_note = f"{history_note} · by {user_id}"
        self._history.record_snapshot(
            saved,
            RevisionSource.MANUAL_EDIT,
            note=history_note,
        )
        return saved

    def get_mission_bundle(self, mission_id: UUID) -> MissionGenerationResult:
        mission = self._require_mission(mission_id)
        return MissionGenerationResult(
            mission=mission,
            knowledge_gaps=self._missions.list_knowledge_gaps(mission_id),
            assumptions=self._missions.list_assumptions(mission_id),
            clarifying_questions=self._missions.list_clarifying_questions(mission_id),
            design_questions=self._missions.list_design_questions(mission_id),
        )

    def _persist_generation(
        self,
        project_id: UUID,
        draft: MissionGenerationDraft,
        *,
        previous: ProjectMission | None = None,
        change_source: RevisionSource = RevisionSource.GENERATED,
        concept_mode: bool = False,
    ) -> MissionGenerationResult:
        facts = self._fact_ledger.get_ledger(project_id)
        fact_models = [
            entry.fact for entry in facts.entries if entry.fact is not None
        ] + list(facts.extra_facts)

        validation = validate_mission_draft(draft, fact_models, concept_mode=concept_mode)
        if not validation.ok:
            raise WorkflowError("; ".join(validation.errors))

        version = (previous.version + 1) if previous is not None else 1
        parsed = parse_mission_draft(
            draft,
            project_id=project_id,
            facts=fact_models,
            version=version,
            concept_mode=concept_mode,
        )
        apply_mission_lineage(parsed.mission, previous)
        saved_mission = self._missions.save_mission(parsed.mission)
        self._history.record_snapshot(saved_mission, change_source)

        gaps = [self._missions.save_knowledge_gap(item) for item in parsed.knowledge_gaps]
        assumptions = [self._missions.save_assumption(item) for item in parsed.assumptions]
        questions = [
            self._missions.save_clarifying_question(item) for item in parsed.clarifying_questions
        ]
        design_questions = [
            self._missions.save_design_question(item) for item in parsed.design_questions
        ]

        return MissionGenerationResult(
            mission=saved_mission,
            knowledge_gaps=gaps,
            assumptions=assumptions,
            clarifying_questions=questions,
            design_questions=design_questions,
            warnings=list(validation.warnings) + parsed.validation_warnings,
        )

    def _clear_mission_artifacts(self, mission_id: UUID) -> None:
        self._missions.delete_workstreams_for_mission(mission_id)
        self._missions.delete_deliverable_plans_for_mission(mission_id)

    def _build_context(self, project_id: UUID, query: str) -> str:
        return build_project_context(
            self._session,
            project_id,
            query=query,
            settings=self._settings,
        )

    def _build_fact_summary(self, project_id: UUID) -> str:
        ledger = self._fact_ledger.get_ledger(project_id)
        lines: list[str] = []
        for entry in ledger.entries:
            if entry.fact is None:
                lines.append(f"- [缺失] {entry.label} ({entry.key})")
            else:
                fact = entry.fact
                status = "已确认" if fact.is_confirmed else fact.verification_status.value
                unit = f" {fact.unit}" if fact.unit else ""
                lines.append(f"- [{status}] {fact.label}: {fact.value}{unit} (key={fact.key})")
        for fact in ledger.extra_facts:
            lines.append(f"- [extra] {fact.label}: {fact.value}")
        if ledger.conflict_count:
            lines.append(f"【冲突事实组数: {ledger.conflict_count}】")
        if ledger.missing_standard_keys:
            lines.append("【缺失标准字段: " + ", ".join(ledger.missing_standard_keys) + "】")
        return "\n".join(lines) if lines else "暂无已提取事实"

    def _require_project(self, project_id: UUID) -> Project:
        project = self._projects.get_by_id(project_id)
        if project is None:
            raise WorkflowError(f"项目 {project_id} 不存在")
        return project

    def _require_mission(self, mission_id: UUID) -> ProjectMission:
        mission = self._missions.get_mission(mission_id)
        if mission is None:
            raise WorkflowError(f"任务理解 {mission_id} 不存在")
        return mission


class NarrativeModeSuggestion(DomainModel):
    mode: ArchitecturalNarrativeMode
    reason: str


def suggest_narrative_mode(mission: ProjectMission) -> NarrativeModeSuggestion:
    """Suggest content organization from mission semantics, never visual style."""
    context = " ".join(
        [mission.decision_context, mission.task_statement, *mission.primary_problems]
    ).lower()
    if any(token in context for token in ("分期", "实施", "roadmap", "phase")):
        return NarrativeModeSuggestion(
            mode=ArchitecturalNarrativeMode.PHASED_IMPLEMENTATION,
            reason="任务强调实施次序与阶段成果，需要说明各阶段如何逐步解锁。",
        )
    if any(token in context for token in ("比较", "比选", "option", "scheme")):
        return NarrativeModeSuggestion(
            mode=ArchitecturalNarrativeMode.OPTION_COMPARISON,
            reason="任务包含方案比较或选择，需要用统一标准形成可审议结论。",
        )
    if any(token in context for token in ("技术", "规范", "technical", "compliance")):
        return NarrativeModeSuggestion(
            mode=ArchitecturalNarrativeMode.TECHNICAL_BRIEFING,
            reason="任务以技术依据和合规判断为主，适合技术简报结构。",
        )
    if mission.decisions_required:
        return NarrativeModeSuggestion(
            mode=ArchitecturalNarrativeMode.DECISION_FIRST,
            reason="Mission 已明确待决策事项，应先呈现决策请求，再展开证据与策略。",
        )
    if mission.primary_problems:
        return NarrativeModeSuggestion(
            mode=ArchitecturalNarrativeMode.PROBLEM_SOLUTION,
            reason="Mission 已识别现状问题与期望改变，适合问题—证据—策略叙事。",
        )
    return NarrativeModeSuggestion(
        mode=ArchitecturalNarrativeMode.DESIGN_PROCESS,
        reason="当前任务以设计形成过程为主，适合按背景、策略和方案演进组织。",
    )


def mission_approval_hash(mission: ProjectMission) -> str:
    """Hash human-approved Mission content, including narrative mode.

    Downstream planning sync fields (recommended workstream/deliverable ids) are
    excluded so workstream/deliverable planning does not invalidate approval.
    """
    payload = mission.model_dump(
        mode="json",
        exclude={
            "approval_hash",
            "approval_status",
            "created_at",
            "updated_at",
            "recommended_workstream_ids",
            "recommended_deliverable_ids",
        },
    )
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def is_mission_approval_current(mission: ProjectMission) -> bool:
    """Reject legacy, edited, or tampered approvals at every workflow gate."""
    return (
        mission.approval_status == ApprovalStatus.APPROVED
        and mission.approval_hash is not None
        and mission.approval_hash == mission_approval_hash(mission)
    )


def ensure_mission_approval_current(mission: ProjectMission) -> None:
    """Raise when mission approval is missing, stale, or tampered."""
    if is_mission_approval_current(mission):
        return
    if mission.approval_status != ApprovalStatus.APPROVED:
        raise WorkflowError("任务理解尚未批准，无法继续下游规划。请先批准任务理解。")
    raise WorkflowError("任务理解审批已失效（内容已变更或校验失败），请重新批准后再继续。")

