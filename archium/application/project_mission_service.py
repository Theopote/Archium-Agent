"""Project mission generation and revision service."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from pydantic import Field
from sqlalchemy.orm import Session

from archium.agents._helpers import build_project_context, to_json
from archium.application.fact_ledger_service import FactLedgerService
from archium.application.mission_history_service import MissionHistoryService
from archium.application.mission_lineage import apply_mission_lineage
from archium.application.mission_parser import (
    parse_mission_draft,
    validate_mission_draft,
)
from archium.config.settings import Settings, get_settings
from archium.domain._base import DomainModel
from archium.domain.enums import (
    InterventionScale,
    ProjectDomain,
    ServiceDepth,
    SlideChangeSource,
    TaskNature,
    UncertaintyLevel,
)
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
    ) -> MissionGenerationResult:
        project = self._require_project(project_id)
        if not user_task_description.strip():
            raise WorkflowError("任务描述不能为空")

        context = self._build_context(project_id, user_task_description)
        fact_summary = self._build_fact_summary(project_id)
        draft = self._llm.generate_structured(
            LLMRequest(
                system_prompt=MISSION_SYSTEM_PROMPT,
                user_prompt=build_mission_user_prompt(
                    user_task_description=user_task_description,
                    project_context=context,
                    fact_ledger_summary=fact_summary,
                    project_name=project.name,
                    project_type=project.project_type.value,
                ),
                temperature=0.3,
                json_mode=True,
            ),
            MissionGenerationDraft,
        )
        return self._persist_generation(project_id, draft)

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
            change_source=SlideChangeSource.REGENERATION,
        )
        return result

    def update_mission(self, mission_id: UUID, patch: MissionPatch) -> ProjectMission:
        mission = self._require_mission(mission_id)
        payload = mission.model_dump(mode="json")
        payload.update(patch.model_dump(mode="json", exclude_none=True))
        updated = ProjectMission.model_validate(payload)
        updated.touch()
        saved = self._missions.save_mission(updated)
        self._history.record_snapshot(saved, SlideChangeSource.MANUAL_EDIT)
        return saved

    def approve_mission(self, mission_id: UUID) -> ProjectMission:
        mission = self._require_mission(mission_id)
        mission.approve()
        saved = self._missions.save_mission(mission)
        self._history.record_snapshot(
            saved,
            SlideChangeSource.MANUAL_EDIT,
            note="批准任务理解",
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
        change_source: SlideChangeSource = SlideChangeSource.GENERATED,
    ) -> MissionGenerationResult:
        facts = self._fact_ledger.get_ledger(project_id)
        fact_models = [
            entry.fact for entry in facts.entries if entry.fact is not None
        ] + list(facts.extra_facts)

        validation = validate_mission_draft(draft, fact_models)
        if not validation.ok:
            raise WorkflowError("; ".join(validation.errors))

        version = (previous.version + 1) if previous is not None else 1
        parsed = parse_mission_draft(
            draft,
            project_id=project_id,
            facts=fact_models,
            version=version,
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
