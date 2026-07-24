"""Unit tests for planning workflow autonomous research node."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

from archium.application.autonomous_research_service import AutonomousResearchResult
from archium.domain.enums import InformationOrigin, InformationReliability, ProjectOriginMode
from archium.domain.project_knowledge import ProjectKnowledgeItem
from archium.workflow.planning_nodes import PlanningWorkflowNodes, PlanningWorkflowRuntime
from archium.workflow.planning_state import PlanningWorkflowState


def test_run_autonomous_research_skips_for_existing_project(db_session, test_settings) -> None:
    runtime = PlanningWorkflowRuntime(
        db_session,
        MagicMock(),
        settings=test_settings,
    )
    nodes = PlanningWorkflowNodes(runtime)
    state: PlanningWorkflowState = {
        "project_id": str(uuid4()),
        "workflow_run_id": str(uuid4()),
        "origin_mode": ProjectOriginMode.EXISTING_PROJECT.value,
        "mission_id": str(uuid4()),
        "warnings": [],
    }

    with patch(
        "archium.application.autonomous_research_service.AutonomousResearchService.research_for_mission"
    ) as research_mock:
        result = nodes.run_autonomous_research(state)

    research_mock.assert_not_called()
    assert result["current_step"] == "planning_autonomous_research"


def test_run_autonomous_research_runs_for_concept_exploration(db_session, test_settings) -> None:
    runtime = PlanningWorkflowRuntime(
        db_session,
        MagicMock(),
        settings=test_settings,
    )
    nodes = PlanningWorkflowNodes(runtime)
    mission_id = uuid4()
    state: PlanningWorkflowState = {
        "project_id": str(uuid4()),
        "workflow_run_id": str(uuid4()),
        "origin_mode": ProjectOriginMode.CONCEPT_EXPLORATION.value,
        "mission_id": str(mission_id),
        "warnings": [],
    }
    fake_item = ProjectKnowledgeItem(
        project_id=uuid4(),
        statement="研究摘要",
        origin=InformationOrigin.PUBLIC_RESEARCH,
        reliability=InformationReliability.UNVERIFIED,
    )
    fake_result = AutonomousResearchResult(
        project_id=uuid4(),
        mission_id=mission_id,
        items=[fake_item],
        search_hit_count=2,
        search_provider="stub",
    )

    with patch(
        "archium.application.autonomous_research_service.AutonomousResearchService.research_for_mission",
        return_value=fake_result,
    ) as research_mock:
        result = nodes.run_autonomous_research(state)

    research_mock.assert_called_once_with(mission_id)
    assert result["autonomous_research_item_count"] == 1
    assert any("自动研究" in warning for warning in result.get("warnings", []))


def test_run_autonomous_research_runs_for_research_programming(db_session, test_settings) -> None:
    runtime = PlanningWorkflowRuntime(
        db_session,
        MagicMock(),
        settings=test_settings,
    )
    nodes = PlanningWorkflowNodes(runtime)
    mission_id = uuid4()
    state: PlanningWorkflowState = {
        "project_id": str(uuid4()),
        "workflow_run_id": str(uuid4()),
        "origin_mode": ProjectOriginMode.RESEARCH_PROGRAMMING.value,
        "mission_id": str(mission_id),
        "warnings": [],
    }

    with patch(
        "archium.application.autonomous_research_service.AutonomousResearchService.research_for_mission",
        return_value=AutonomousResearchResult(
            project_id=uuid4(),
            mission_id=mission_id,
            items=[],
            search_hit_count=0,
            search_provider="stub",
        ),
    ) as research_mock:
        nodes.run_autonomous_research(state)

    research_mock.assert_called_once_with(mission_id)
