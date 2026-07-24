"""Unit tests for mission / deliverable / workstream revision history."""

from __future__ import annotations

from uuid import UUID

import pytest
from archium.application.mission_history_service import (
    DeliverablePlanHistoryService,
    MissionHistoryService,
    WorkstreamHistoryService,
)
from archium.application.mission_snapshots import (
    diff_mission_snapshots,
    mission_to_snapshot,
)
from archium.application.project_mission_service import ProjectMissionService
from archium.application.workstream_planning_service import WorkstreamPlanningService
from archium.domain.enums import RevisionEntityType, RevisionSource, WorkstreamType
from archium.domain.project import Project
from archium.domain.project_mission import ProjectMission
from archium.domain.workstream import Workstream
from archium.infrastructure.database.mission_repositories import MissionRepository
from archium.infrastructure.database.repositories import ProjectRepository
from archium.infrastructure.llm import LLMRequest, MockLLMProvider
from sqlalchemy.orm import Session

from tests.fixtures.mission_approval import approve_generated_mission
from tests.fixtures.mock_mission_responses import TEMPLE_MISSION_JSON
from tests.fixtures.mock_workstream_responses import TEMPLE_WORKSTREAM_PLAN_JSON


def _selector(request: LLMRequest) -> str | None:
    if "WorkstreamPlan JSON" in request.user_prompt:
        return TEMPLE_WORKSTREAM_PLAN_JSON
    if "ProjectMission JSON" in request.user_prompt:
        return TEMPLE_MISSION_JSON
    return None


@pytest.fixture
def llm() -> MockLLMProvider:
    return MockLLMProvider(selector=_selector)


@pytest.fixture
def project_id(db_session: Session) -> UUID:
    return ProjectRepository(db_session).create(Project(name="历史修订测试")).id


TEMPLE_TASK = (
    "三原县清凉寺历史上多次被毁，现在希望重新建设。"
    "目前只有部分地方志和现场照片，甲方还没有明确建筑面积。"
    "希望先形成前期策划、案例研究和概念设计汇报。"
)


def test_mission_snapshot_and_field_diff(project_id: UUID) -> None:
    from archium.domain.enums import ServiceDepth, TaskNature, UncertaintyLevel
    from archium.domain.project_mission import Stakeholder

    mission = ProjectMission(
        project_id=project_id,
        title="初版",
        task_statement="形成前期策划",
        task_natures=[TaskNature.NEW_BUILD],
        requested_service_depths=[ServiceDepth.CONCEPT_PLANNING],
        uncertainty_level=UncertaintyLevel.MEDIUM,
        version=1,
    )
    updated = mission.model_copy(
        update={
            "title": "修订版",
            "version": 2,
            "task_natures": [TaskNature.RENOVATION, TaskNature.STRATEGY],
            "requested_service_depths": [
                ServiceDepth.PROJECT_DIAGNOSIS,
                ServiceDepth.CONCEPT_PLANNING,
            ],
            "uncertainty_level": UncertaintyLevel.HIGH,
            "stakeholders": [Stakeholder(name="院方", role="业主", concerns=["不停业"])],
        }
    )
    diff = diff_mission_snapshots(
        mission_to_snapshot(mission),
        mission_to_snapshot(updated),
        before_label="before",
        after_label="after",
        entity_id=mission.id,
    )
    fields = {change.field for change in diff.changes}
    assert "title" in fields
    assert "version" in fields
    assert "task_natures" in fields
    assert "requested_service_depths" in fields
    assert "uncertainty_level" in fields
    assert "stakeholders" in fields
    assert diff.has_changes


def test_mission_history_on_generate_and_regenerate(
    db_session: Session,
    llm: MockLLMProvider,
    project_id: UUID,
) -> None:
    service = ProjectMissionService(db_session, llm)
    history = MissionHistoryService(db_session)

    generated = service.generate_mission(project_id, TEMPLE_TASK)
    revisions = history.list_revisions(generated.mission.id)
    assert len(revisions) == 1
    assert revisions[0].entity_type == RevisionEntityType.MISSION
    assert revisions[0].change_source == RevisionSource.GENERATED
    assert revisions[0].presentation_id is None

    regenerated = service.regenerate_mission(
        generated.mission.id,
        "请更强调历史研究与案例比较",
    )
    lineage_revisions = history.list_revisions_by_lineage(regenerated.mission.lineage_id)
    assert len(lineage_revisions) >= 3  # generated + archive + regeneration
    sources = {item.change_source for item in lineage_revisions}
    assert RevisionSource.REGENERATION in sources

    latest = max(lineage_revisions, key=lambda item: item.revision_number)
    previous_diff = history.diff_with_previous(latest.id)
    assert previous_diff is not None


def test_workstream_recommendation_reason_persisted(
    db_session: Session,
    llm: MockLLMProvider,
    project_id: UUID,
) -> None:
    mission = ProjectMissionService(db_session, llm).generate_mission(project_id, TEMPLE_TASK)
    mission_service = ProjectMissionService(db_session, llm)
    approve_generated_mission(mission_service, mission.mission)
    result = WorkstreamPlanningService(db_session, llm).plan_workstreams(mission.mission.id)
    historical = next(
        item for item in result.workstreams if item.workstream_type == WorkstreamType.HISTORICAL_RESEARCH
    )
    assert "历史" in historical.recommendation_reason

    fetched = MissionRepository(db_session).list_workstreams(mission.mission.id)
    by_type = {item.workstream_type: item for item in fetched}
    assert by_type[WorkstreamType.HISTORICAL_RESEARCH].recommendation_reason == (
        historical.recommendation_reason
    )

    history = WorkstreamHistoryService(db_session)
    revisions = history.list_revisions_by_lineage(historical.lineage_id)
    assert len(revisions) == 1
    assert revisions[0].snapshot.get("recommendation_reason") == historical.recommendation_reason


def test_workstream_history_manual_select(
    db_session: Session,
    project_id: UUID,
) -> None:
    mission = MissionRepository(db_session).save_mission(
        ProjectMission(
            project_id=project_id,
            title="选型历史",
            task_statement="测试选中快照",
        )
    )
    ws = MissionRepository(db_session).save_workstream(
        Workstream(
            project_id=project_id,
            mission_id=mission.id,
            title="历史研究",
            workstream_type=WorkstreamType.HISTORICAL_RESEARCH,
            objective="梳理沿革",
            recommendation_reason="重建依赖历史依据",
        )
    )
    service = WorkstreamPlanningService(
        db_session,
        MockLLMProvider(selector=lambda _r: None),
    )
    selected = service.select_workstream(ws.id)
    assert selected.selected is True
    revisions = WorkstreamHistoryService(db_session).list_revisions_by_lineage(ws.lineage_id)
    assert any(item.change_source == RevisionSource.MANUAL_EDIT for item in revisions)


def test_deliverable_plan_history_service_records(
    db_session: Session,
    project_id: UUID,
) -> None:
    from archium.domain.deliverable import DeliverablePlan, PlannedDeliverable
    from archium.domain.enums import DeliverableType

    mission = MissionRepository(db_session).save_mission(
        ProjectMission(
            project_id=project_id,
            title="成果历史",
            task_statement="测试成果修订",
        )
    )
    plan = MissionRepository(db_session).save_deliverable_plan(
        DeliverablePlan(
            project_id=project_id,
            mission_id=mission.id,
            deliverables=[
                PlannedDeliverable(
                    id="del-ppt",
                    title="概念汇报",
                    deliverable_type=DeliverableType.PRESENTATION,
                    purpose="汇报",
                    selected=True,
                )
            ],
        )
    )
    history = DeliverablePlanHistoryService(db_session)
    history.record_snapshot(plan, RevisionSource.GENERATED)
    revisions = history.list_revisions_by_lineage(plan.lineage_id)
    assert len(revisions) == 1
    assert revisions[0].entity_type == RevisionEntityType.DELIVERABLE_PLAN
