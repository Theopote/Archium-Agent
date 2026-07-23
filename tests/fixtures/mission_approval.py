"""Approve a generated mission so require_ready planning gates can proceed in tests."""

from __future__ import annotations

from archium.application.project_mission_service import ProjectMissionService
from archium.domain.project_mission import ProjectMission


def approve_generated_mission(
    mission_service: ProjectMissionService,
    mission: ProjectMission,
) -> ProjectMission:
    """Mark mission approved with a current approval hash (test helper)."""
    return mission_service.approve_mission(mission.id)
