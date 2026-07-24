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


def test_concept_exploration_primary_page_is_exploration() -> None:
    profile = profile_for(ArchitecturalWorkspaceMode.CONCEPT_EXPLORATION)
    assert profile.primary_page_key == "concept-exploration"


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


def test_partial_knowledge_routes_by_context_not_origin_only(db_session) -> None:
    from archium.domain.intent.knowledge_state import KnowledgeMaturityStage, KnowledgeState

    project = ProjectRepository(db_session).create(
        Project(
            name="医院改造",
            description="西安某医院老院区改造，有一张照片和旧介绍",
            origin_mode=ProjectOriginMode.EXISTING_PROJECT,
            knowledge_state=KnowledgeState(
                completeness_score=0.32,
                maturity_stage=KnowledgeMaturityStage.DESIGN_ANALYSIS,
                evidence_ratio=0.2,
                assumption_ratio=0.75,
                known={"location": "西安", "type": "医院改造"},
                unknown=["规模", "历史"],
                missing_information=["规模", "历史"],
            ),
        )
    )
    db_session.commit()
    service = WorkspaceModeService(db_session)
    mode = service.resolve_mode(project.id)
    assert mode == ArchitecturalWorkspaceMode.CONCEPT_EXPLORATION
    assert service.resolve_primary_page_key(project.id) == "project-mission"
