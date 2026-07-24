"""Golden scenarios M1–M6 for mission-first adaptive planning."""

from __future__ import annotations

from pathlib import Path

import pytest
from archium.application.deliverable_execution import (
    ArtifactExecutionPlan,
    DeliverableExecutionRouter,
)
from archium.application.deliverable_planning_service import DeliverablePlanningService
from archium.application.mission_to_presentation_request import (
    MissionPresentationBridge,
    build_presentation_bridge,
)
from archium.application.project_mission_service import ProjectMissionService
from archium.application.workstream_planning_service import WorkstreamPlanningService
from archium.domain.enums import DeliverableType
from archium.exceptions import WorkflowError
from archium.infrastructure.llm import MockLLMProvider
from sqlalchemy.orm import Session
from tests.fixtures.mission_approval import approve_generated_mission
from tests.fixtures.mock_mission_golden import CASE_MOCKS, make_mission_case_selector
from tests.golden.mission.assertions import assert_mission_expectations
from tests.golden.mission.loader import (
    list_mission_case_paths,
    load_mission_case,
    seed_mission_case,
)

pytestmark = pytest.mark.regression


@pytest.mark.parametrize("case_path", list_mission_case_paths(), ids=lambda p: p.stem)
def test_mission_golden_case(
    db_session: Session,
    test_settings: object,
    case_path: Path,
) -> None:
    case, project = seed_mission_case(db_session, case_path)
    llm = MockLLMProvider(selector=make_mission_case_selector(case.id))

    mission_service = ProjectMissionService(db_session, llm, settings=test_settings)  # type: ignore[arg-type]
    workstream_service = WorkstreamPlanningService(db_session, llm, settings=test_settings)  # type: ignore[arg-type]
    deliverable_service = DeliverablePlanningService(db_session, llm, settings=test_settings)  # type: ignore[arg-type]

    generation = mission_service.generate_mission(project.id, case.task_description)
    approve_generated_mission(mission_service, generation.mission)
    workstream_result = workstream_service.plan_workstreams(
        generation.mission.id,
        require_ready=True,
    )
    deliverable_result = deliverable_service.plan_deliverables(
        generation.mission.id,
        require_ready=True,
    )
    execution_plans: list[ArtifactExecutionPlan] = DeliverableExecutionRouter().route_plan(
        deliverable_result.mission,
        deliverable_result.plan,
        workstreams=deliverable_result.workstreams,
    )
    bridge: MissionPresentationBridge | None = None
    has_presentation = any(
        item.supported and item.deliverable_type == DeliverableType.PRESENTATION
        for item in execution_plans
    )
    if has_presentation:
        bridge = build_presentation_bridge(
            deliverable_result.mission,
            plan=deliverable_result.plan,
            workstreams=deliverable_result.workstreams,
        )
    elif case.expectations.get("presentation_deliverable_required"):
        pytest.fail("expected a selected presentation deliverable for bridge")
    else:
        with pytest.raises(
            WorkflowError,
            match="不会自动转换成 PresentationRequest|未找到已选中的 presentation",
        ):
            build_presentation_bridge(
                deliverable_result.mission,
                plan=deliverable_result.plan,
                workstreams=deliverable_result.workstreams,
            )

    assert_mission_expectations(
        expectations=case.expectations,
        generation=generation,
        workstreams=workstream_result.workstreams,
        plan=deliverable_result.plan,
        bridge=bridge,
        execution_plans=execution_plans,
    )


def test_mission_golden_manifests_load() -> None:
    paths = list_mission_case_paths()
    assert len(paths) == 6
    ids = {load_mission_case(path).id for path in paths}
    assert ids == set(CASE_MOCKS)
    assert ids == {
        "case_m1_temple",
        "case_m2_library",
        "case_m3_hospital_env",
        "case_m4_village",
        "case_m5_fire_station",
        "case_m6_green_campus",
    }
