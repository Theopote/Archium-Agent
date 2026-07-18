"""Lineage helpers for ProjectMission regeneration."""

from __future__ import annotations

from archium.domain.project_mission import MISSION_LOGICAL_KEY, ProjectMission


def apply_mission_lineage(mission: ProjectMission, previous: ProjectMission | None) -> ProjectMission:
    mission.logical_key = MISSION_LOGICAL_KEY
    if previous is None:
        return mission
    mission.lineage_id = previous.lineage_id
    mission.version = previous.version + 1
    return mission
