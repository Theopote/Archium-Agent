import pytest
from archium.application.workflow_route_service import WorkflowRouteService
from archium.domain.workflow_route import PresentationWorkflowRoute
from archium.exceptions import WorkflowError


def test_route_service_rejects_missing_route_inputs() -> None:
    with pytest.raises(WorkflowError, match="native_template"):
        WorkflowRouteService().validate_inputs(
            PresentationWorkflowRoute.FILL_NATIVE_TEMPLATE,
            {"project_knowledge"},
        )


def test_route_service_prevents_cross_route_execution() -> None:
    with pytest.raises(WorkflowError, match="dedicated workflow"):
        WorkflowRouteService().require_route(
            PresentationWorkflowRoute.BEAUTIFY_EXISTING_DECK,
            PresentationWorkflowRoute.GENERATE_FROM_PROJECT,
        )

