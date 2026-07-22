import pytest
from archium.application.workflow_route_service import (
    RouteImplementationStatus,
    WorkflowRouteService,
)
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


def test_every_route_has_an_honest_registration() -> None:
    service = WorkflowRouteService()
    registrations = [service.registration(route) for route in PresentationWorkflowRoute]
    assert len(registrations) == len(PresentationWorkflowRoute)
    assert service.registration(PresentationWorkflowRoute.RECOVER_IMAGE_DECK).handler_key == (
        "slide_recovery_workflow"
    )


def test_partial_native_template_fill_is_not_claimed_available() -> None:
    service = WorkflowRouteService()
    registration = service.registration(PresentationWorkflowRoute.FILL_NATIVE_TEMPLATE)
    assert registration.status == RouteImplementationStatus.PARTIAL
    with pytest.raises(WorkflowError, match="does not yet preserve native OOXML masters"):
        service.require_available(PresentationWorkflowRoute.FILL_NATIVE_TEMPLATE)


def test_available_routes_have_executable_handler_keys() -> None:
    registrations = WorkflowRouteService().available_routes()
    assert {registration.route for registration in registrations} == {
        PresentationWorkflowRoute.GENERATE_FROM_PROJECT,
        PresentationWorkflowRoute.RECOVER_IMAGE_DECK,
        PresentationWorkflowRoute.DISTILL_TEMPLATE,
    }
    assert all(registration.handler_key for registration in registrations)


def test_resolve_handler_key_combines_availability_and_input_checks() -> None:
    service = WorkflowRouteService()
    assert service.resolve_handler_key(
        PresentationWorkflowRoute.RECOVER_IMAGE_DECK,
        {"image_deck"},
    ) == "slide_recovery_workflow"
    with pytest.raises(WorkflowError, match="image_deck"):
        service.resolve_handler_key(PresentationWorkflowRoute.RECOVER_IMAGE_DECK, set())
