"""Dynamic workstream planning for approved project missions."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy.orm import Session

from archium.agents._helpers import build_project_context, to_json
from archium.application.mission_clarification_service import MissionClarificationService
from archium.application.workstream_parser import (
    parse_workstream_plan_draft,
    validate_workstream_plan_draft,
)
from archium.config.settings import Settings, get_settings
from archium.domain.enums import WorkstreamStatus
from archium.domain.project_mission import ProjectMission
from archium.domain.workstream import Workstream
from archium.exceptions import WorkflowError
from archium.infrastructure.database.mission_repositories import MissionRepository
from archium.infrastructure.llm.base import LLMProvider, LLMRequest
from archium.infrastructure.llm.workstream_schemas import WorkstreamPlanDraft
from archium.prompts.workstream_plan import (
    WORKSTREAM_PLAN_SYSTEM_PROMPT,
    build_workstream_plan_user_prompt,
)


@dataclass
class WorkstreamPlanResult:
    mission: ProjectMission
    workstreams: list[Workstream] = field(default_factory=list)
    planning_notes: str = ""
    warnings: list[str] = field(default_factory=list)

    @property
    def selected_workstreams(self) -> list[Workstream]:
        return [item for item in self.workstreams if item.selected]


class WorkstreamPlanningService:
    """Generate and manage dynamic workstreams for a project mission."""

    def __init__(
        self,
        session: Session,
        llm: LLMProvider,
        *,
        settings: Settings | None = None,
        clarification_service: MissionClarificationService | None = None,
    ) -> None:
        self._session = session
        self._llm = llm
        self._settings = settings or get_settings()
        self._missions = MissionRepository(session)
        self._clarification = clarification_service or MissionClarificationService(
            session, llm, settings=self._settings
        )

    def plan_workstreams(
        self,
        mission_id: UUID,
        *,
        user_priorities: list[str] | None = None,
        replace_existing: bool = True,
        require_ready: bool = True,
    ) -> WorkstreamPlanResult:
        mission = self._require_mission(mission_id)
        if require_ready:
            self._clarification.ensure_can_continue(mission_id)

        gaps = self._missions.list_knowledge_gaps(mission_id)
        assumptions = self._missions.list_assumptions(mission_id)
        documents_summary = build_project_context(
            self._session,
            mission.project_id,
            query=mission.task_statement,
            settings=self._settings,
        )

        draft = self._llm.generate_structured(
            LLMRequest(
                system_prompt=WORKSTREAM_PLAN_SYSTEM_PROMPT,
                user_prompt=build_workstream_plan_user_prompt(
                    mission_json=to_json(mission),
                    gaps_summary=self._format_gaps(gaps),
                    assumptions_summary=self._format_assumptions(assumptions),
                    priorities_summary="\n".join(f"- {item}" for item in (user_priorities or [])),
                    documents_summary=documents_summary,
                ),
                temperature=0.3,
                json_mode=True,
            ),
            WorkstreamPlanDraft,
        )

        errors = validate_workstream_plan_draft(draft)
        if errors:
            raise WorkflowError("; ".join(errors))

        parsed = parse_workstream_plan_draft(
            draft,
            project_id=mission.project_id,
            mission_id=mission.id,
            knowledge_gaps=gaps,
        )

        if replace_existing:
            self._missions.delete_workstreams_for_mission(mission_id)

        saved = [self._missions.save_workstream(item) for item in parsed.workstreams]
        mission = self._sync_recommended_ids(mission, saved)
        return WorkstreamPlanResult(
            mission=mission,
            workstreams=saved,
            planning_notes=parsed.planning_notes,
            warnings=parsed.warnings,
        )

    def list_workstreams(self, mission_id: UUID) -> list[Workstream]:
        self._require_mission(mission_id)
        return self._missions.list_workstreams(mission_id)

    def select_workstream(self, workstream_id: UUID) -> Workstream:
        workstream = self._require_workstream(workstream_id)
        workstream.select()
        return self._missions.save_workstream(workstream)

    def deselect_workstream(self, workstream_id: UUID) -> Workstream:
        workstream = self._require_workstream(workstream_id)
        workstream.deselect()
        return self._missions.save_workstream(workstream)

    def set_workstream_selection(
        self,
        mission_id: UUID,
        selected_ids: list[UUID],
    ) -> list[Workstream]:
        selected_set = set(selected_ids)
        updated: list[Workstream] = []
        for workstream in self.list_workstreams(mission_id):
            if workstream.id in selected_set:
                workstream.select()
            else:
                workstream.deselect()
            updated.append(self._missions.save_workstream(workstream))
        return updated

    def add_workstream(self, workstream: Workstream) -> Workstream:
        mission = self._require_mission(workstream.mission_id)
        if workstream.project_id != mission.project_id:
            raise WorkflowError("工作路径的 project_id 与 mission 不匹配")
        return self._missions.save_workstream(workstream)

    def skip_workstream(self, workstream_id: UUID) -> Workstream:
        workstream = self._require_workstream(workstream_id)
        workstream.selected = False
        workstream.status = WorkstreamStatus.SKIPPED
        workstream.touch()
        return self._missions.save_workstream(workstream)

    def get_plan_result(self, mission_id: UUID) -> WorkstreamPlanResult:
        mission = self._require_mission(mission_id)
        return WorkstreamPlanResult(
            mission=mission,
            workstreams=self._missions.list_workstreams(mission_id),
        )

    def _sync_recommended_ids(
        self,
        mission: ProjectMission,
        workstreams: list[Workstream],
    ) -> ProjectMission:
        recommended_ids = [item.id for item in workstreams if item.recommended]
        updated = mission.model_copy(update={"recommended_workstream_ids": recommended_ids})
        updated.touch()
        return self._missions.save_mission(updated)

    def _format_gaps(self, gaps: list) -> str:
        if not gaps:
            return ""
        lines = []
        for index, gap in enumerate(gaps):
            lines.append(
                f"[{index}] {gap.question} | status={gap.status.value} | "
                f"blocking={gap.blocking} | category={gap.category.value}"
            )
        return "\n".join(lines)

    def _format_assumptions(self, assumptions: list) -> str:
        if not assumptions:
            return ""
        return "\n".join(
            f"- [{item.status.value}] {item.statement}（原因：{item.reason}）"
            for item in assumptions
        )

    def _require_mission(self, mission_id: UUID) -> ProjectMission:
        mission = self._missions.get_mission(mission_id)
        if mission is None:
            raise WorkflowError(f"任务理解 {mission_id} 不存在")
        return mission

    def _require_workstream(self, workstream_id: UUID) -> Workstream:
        workstream = self._missions.get_workstream(workstream_id)
        if workstream is None:
            raise WorkflowError(f"工作路径 {workstream_id} 不存在")
        return workstream
