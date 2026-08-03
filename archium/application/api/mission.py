"""/mission — project mission facade."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.project_mission_service import (
    MissionGenerationResult,
    MissionPatch,
    ProjectMissionService,
)
from archium.domain.deliverable import DeliverablePlan
from archium.domain.knowledge_gap import Assumption, ClarifyingQuestion, KnowledgeGap
from archium.domain.project_mission import ProjectMission
from archium.domain.workstream import Workstream
from archium.infrastructure.database.mission_repositories import MissionRepository
from archium.infrastructure.llm.factory import create_llm_provider


class MissionApi:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._missions = MissionRepository(session)
        self._service: ProjectMissionService | None = None

    def _mission_service(self) -> ProjectMissionService:
        if self._service is None:
            self._service = ProjectMissionService(
                self._session,
                create_llm_provider(),
            )
        return self._service

    def list_for_project(self, project_id: UUID) -> list[ProjectMission]:
        return self._missions.list_missions_by_project(project_id)

    def get(self, mission_id: UUID) -> ProjectMission | None:
        return self._missions.get_mission(mission_id)

    def list_deliverable_plans(self, mission_id: UUID) -> list[DeliverablePlan]:
        return self._missions.list_deliverable_plans(mission_id)

    def get_deliverable_plan(self, plan_id: UUID) -> DeliverablePlan | None:
        return self._missions.get_deliverable_plan(plan_id)

    def get_approved_deliverable_plan(self, mission_id: UUID) -> DeliverablePlan | None:
        return self._missions.get_approved_deliverable_plan(mission_id)

    def list_workstreams(self, mission_id: UUID) -> list[Workstream]:
        return self._missions.list_workstreams(mission_id)

    def list_clarifying_questions(self, mission_id: UUID) -> list[ClarifyingQuestion]:
        return self._missions.list_clarifying_questions(mission_id)

    def list_knowledge_gaps(self, mission_id: UUID) -> list[KnowledgeGap]:
        return self._missions.list_knowledge_gaps(mission_id)

    def list_assumptions(self, mission_id: UUID) -> list[Assumption]:
        return self._missions.list_assumptions(mission_id)

    def get_bundle(self, mission_id: UUID) -> MissionGenerationResult:
        return self._mission_service().get_mission_bundle(mission_id)

    def update(self, mission_id: UUID, patch: MissionPatch) -> ProjectMission:
        return self._mission_service().update_mission(mission_id, patch)

    def approve(self, mission_id: UUID, **kwargs) -> ProjectMission:
        return self._mission_service().approve_mission(mission_id, **kwargs)
