"""Unit tests for Architectural Workspace four-mode resolution."""

from __future__ import annotations

import pytest

from archium.application.workspace_mode_service import (
    WorkspaceModeService,
    origin_to_default_workspace_mode,
    profile_for,
)
from archium.domain.concept_direction import ConceptDirection
from archium.domain.enums import (
    ArchitecturalWorkspaceMode,
    ConceptDirectionStatus,
    ProjectOriginMode,
)
from archium.domain.project import Project
from archium.domain.project_mission import ProjectMission
from archium.exceptions import WorkflowError
from archium.infrastructure.database.mission_repositories import MissionRepository
from archium.infrastructure.database.repositories import (
    ConceptDirectionRepository,
    ProjectRepository,
)


@pytest.mark.parametrize(
    ("origin", "expected"),
    [
        (ProjectOriginMode.EXISTING_PROJECT, ArchitecturalWorkspaceMode.EXISTING_PROJECT),
        (ProjectOriginMode.CONCEPT_EXPLORATION, ArchitecturalWorkspaceMode.CONCEPT_EXPLORATION),
        (ProjectOriginMode.RESEARCH_PROGRAMMING, ArchitecturalWorkspaceMode.RESEARCH_PROGRAMMING),
    ],
)
def test_origin_maps_to_default_workspace_mode(origin, expected) -> None:
    assert origin_to_default_workspace_mode(origin) == expected
    assert profile_for(expected).title


def test_concept_project_elevates_to_design_iteration_when_directions_exist(
    db_session,
) -> None:
    project = ProjectRepository(db_session).create(
        Project(name="概念", origin_mode=ProjectOriginMode.CONCEPT_EXPLORATION)
    )
    mission = MissionRepository(db_session).save_mission(
        ProjectMission(
            project_id=project.id,
            title="文化中心",
            task_statement="探索概念",
        )
    )
    service = WorkspaceModeService(db_session)
    assert service.resolve_mode(project.id) == ArchitecturalWorkspaceMode.CONCEPT_EXPLORATION

    ConceptDirectionRepository(db_session).create(
        ConceptDirection(
            project_id=project.id,
            mission_id=mission.id,
            title="台地聚落",
            summary="沿台地展开",
            status=ConceptDirectionStatus.DRAFT,
        )
    )
    db_session.commit()

    assert service.resolve_mode(project.id) == ArchitecturalWorkspaceMode.DESIGN_ITERATION
    assert ArchitecturalWorkspaceMode.DESIGN_ITERATION in service.available_modes(project.id)


def test_existing_project_cannot_override_to_design_iteration(db_session) -> None:
    project = ProjectRepository(db_session).create(
        Project(name="改造", origin_mode=ProjectOriginMode.EXISTING_PROJECT)
    )
    service = WorkspaceModeService(db_session)
    with pytest.raises(WorkflowError):
        service.resolve_mode(
            project.id,
            override=ArchitecturalWorkspaceMode.DESIGN_ITERATION,
        )
