"""Enforce presentation workflow boundaries before side effects begin."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from archium.domain._base import DomainModel
from archium.domain.workflow_route import (
    PresentationWorkflowRoute,
    WorkflowRouteContract,
    contract_for_route,
)
from archium.exceptions import WorkflowError


class RouteImplementationStatus(StrEnum):
    AVAILABLE = "available"
    PARTIAL = "partial"
    PLANNED = "planned"


class WorkflowRouteRegistration(DomainModel):
    route: PresentationWorkflowRoute
    status: RouteImplementationStatus
    handler_key: str | None = None
    limitations: list[str] = Field(default_factory=list)


WORKFLOW_ROUTE_REGISTRY: dict[PresentationWorkflowRoute, WorkflowRouteRegistration] = {
    PresentationWorkflowRoute.GENERATE_FROM_PROJECT: WorkflowRouteRegistration(
        route=PresentationWorkflowRoute.GENERATE_FROM_PROJECT,
        status=RouteImplementationStatus.AVAILABLE,
        handler_key="presentation_workflow",
    ),
    PresentationWorkflowRoute.FILL_NATIVE_TEMPLATE: WorkflowRouteRegistration(
        route=PresentationWorkflowRoute.FILL_NATIVE_TEMPLATE,
        status=RouteImplementationStatus.PARTIAL,
        handler_key="reference_slide_editing",
        limitations=[
            "Current fill produces RenderScene output but does not yet preserve native OOXML masters."
        ],
    ),
    PresentationWorkflowRoute.BEAUTIFY_EXISTING_DECK: WorkflowRouteRegistration(
        route=PresentationWorkflowRoute.BEAUTIFY_EXISTING_DECK,
        status=RouteImplementationStatus.PLANNED,
        limitations=["No deck-wide wording/order preservation workflow is registered."],
    ),
    PresentationWorkflowRoute.ENHANCE_NATIVE_DECK: WorkflowRouteRegistration(
        route=PresentationWorkflowRoute.ENHANCE_NATIVE_DECK,
        status=RouteImplementationStatus.PLANNED,
        limitations=["Native notes/transitions/timing package editing is not implemented."],
    ),
    PresentationWorkflowRoute.RECOVER_IMAGE_DECK: WorkflowRouteRegistration(
        route=PresentationWorkflowRoute.RECOVER_IMAGE_DECK,
        status=RouteImplementationStatus.AVAILABLE,
        handler_key="slide_recovery_workflow",
    ),
    PresentationWorkflowRoute.DISTILL_TEMPLATE: WorkflowRouteRegistration(
        route=PresentationWorkflowRoute.DISTILL_TEMPLATE,
        status=RouteImplementationStatus.AVAILABLE,
        handler_key="template_induction",
    ),
}


class WorkflowRouteService:
    """Validate route inputs and prevent accidental cross-route execution."""

    def contract(self, route: PresentationWorkflowRoute) -> WorkflowRouteContract:
        return contract_for_route(route)

    def registration(self, route: PresentationWorkflowRoute) -> WorkflowRouteRegistration:
        return WORKFLOW_ROUTE_REGISTRY[route]

    def require_available(self, route: PresentationWorkflowRoute) -> WorkflowRouteRegistration:
        registration = self.registration(route)
        if registration.status != RouteImplementationStatus.AVAILABLE:
            details = "; ".join(registration.limitations) or "No executable handler is registered."
            raise WorkflowError(
                f"Workflow route {route.value} is {registration.status.value}: {details}"
            )
        return registration

    def available_routes(self) -> list[WorkflowRouteRegistration]:
        return [
            registration
            for registration in WORKFLOW_ROUTE_REGISTRY.values()
            if registration.status == RouteImplementationStatus.AVAILABLE
        ]

    def resolve_handler_key(
        self,
        route: PresentationWorkflowRoute,
        available_inputs: set[str] | frozenset[str],
    ) -> str:
        registration = self.require_available(route)
        self.validate_inputs(route, available_inputs)
        if registration.handler_key is None:
            raise WorkflowError(f"Workflow route {route.value} has no registered handler")
        return registration.handler_key

    def validate_inputs(
        self,
        route: PresentationWorkflowRoute,
        available_inputs: set[str] | frozenset[str],
    ) -> WorkflowRouteContract:
        contract = self.contract(route)
        missing = sorted(contract.required_inputs - frozenset(available_inputs))
        if missing:
            raise WorkflowError(
                f"Workflow route {route.value} is missing required inputs: {', '.join(missing)}"
            )
        return contract

    def require_route(
        self,
        actual: PresentationWorkflowRoute,
        expected: PresentationWorkflowRoute,
    ) -> WorkflowRouteContract:
        if actual != expected:
            raise WorkflowError(
                f"Workflow route {actual.value} cannot run through {expected.value}; "
                "dispatch it to its dedicated workflow"
            )
        return self.contract(actual)
