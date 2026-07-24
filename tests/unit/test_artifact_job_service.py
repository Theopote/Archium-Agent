"""Unit tests for ArtifactJob persistence and generation service."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from archium.application.artifact_job_service import ArtifactJobService
from archium.domain.deliverable import DeliverablePlan, PlannedDeliverable
from archium.domain.enums import (
    ArtifactJobStatus,
    DeliverableType,
    ProjectOriginMode,
    TaskNature,
)
from archium.domain.project import Project
from archium.domain.project_mission import ProjectMission
from archium.exceptions import WorkflowError
from archium.infrastructure.database.mission_repositories import MissionRepository
from archium.infrastructure.database.repositories import ProjectRepository


@pytest.fixture
def mission_with_memo(db_session, tmp_path: Path, test_settings):
    test_settings.output_path = tmp_path
    project = ProjectRepository(db_session).create(
        Project(
            name="策划测试",
            origin_mode=ProjectOriginMode.RESEARCH_PROGRAMMING,
        )
    )
    missions = MissionRepository(db_session)
    mission = missions.save_mission(
        ProjectMission(
            project_id=project.id,
            title="前期策划",
            task_statement="形成投资人沟通备忘录",
            task_natures=[TaskNature.PLANNING],
            decisions_required=["是否分期"],
            key_unknowns=["用地指标"],
            primary_problems=["定位不清"],
        )
    )
    missions.save_deliverable_plan(
        DeliverablePlan(
            project_id=project.id,
            mission_id=mission.id,
            deliverables=[
                PlannedDeliverable(
                    id="del-memo",
                    title="投资人备忘录",
                    deliverable_type=DeliverableType.MEMO,
                    purpose="沟通",
                    selected=True,
                ),
                PlannedDeliverable(
                    id="del-ppt",
                    title="概念汇报",
                    deliverable_type=DeliverableType.PRESENTATION,
                    purpose="汇报",
                    selected=True,
                ),
            ],
        )
    )
    db_session.commit()
    return mission, test_settings


def test_run_memo_persists_completed_job(mission_with_memo, db_session) -> None:
    mission, settings = mission_with_memo
    service = ArtifactJobService(db_session, settings=settings)

    result = service.run_for_deliverable(mission.id, "del-memo")

    assert result.output is not None
    assert "定位不清" in result.output.markdown
    assert result.job.status == ArtifactJobStatus.COMPLETED
    assert result.job.markdown_path
    assert Path(result.job.markdown_path).exists()

    jobs = service.list_jobs_for_mission(mission.id)
    assert len(jobs) == 1
    assert jobs[0].status == ArtifactJobStatus.COMPLETED
    assert jobs[0].request_kind == "memo"


def test_run_rejects_presentation_deliverable(mission_with_memo, db_session) -> None:
    mission, settings = mission_with_memo
    service = ArtifactJobService(db_session, settings=settings)

    with pytest.raises(WorkflowError, match="Presentation"):
        service.run_for_deliverable(mission.id, "del-ppt")
