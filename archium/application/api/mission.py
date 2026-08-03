"""/mission — project mission facade."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.project_mission_service import (
    MissionGenerationResult,
    MissionPatch,
    ProjectMissionService,
)
from archium.domain.project_mission import ProjectMission


class MissionApi:
    def __init__(self, session: Session) -> None:
        self._service = ProjectMissionService(session)

    def get_bundle(self, mission_id: UUID) -> MissionGenerationResult:
        return self._service.get_mission_bundle(mission_id)

    def update(self, mission_id: UUID, patch: MissionPatch) -> ProjectMission:
        return self._service.update_mission(mission_id, patch)

    def approve(self, mission_id: UUID, **kwargs) -> ProjectMission:
        return self._service.approve_mission(mission_id, **kwargs)
