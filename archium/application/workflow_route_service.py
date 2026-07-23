"""Enforce presentation workflow boundaries before side effects begin."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from enum import StrEnum
from typing import Any

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


class RoutePreservationReport(DomainModel):
    """Executable result of comparing a route's protected artifacts."""

    route: PresentationWorkflowRoute
    valid: bool
    preserved_fields: frozenset[str] = Field(default_factory=frozenset)
    missing_before_fields: list[str] = Field(default_factory=list)
    missing_after_fields: list[str] = Field(default_factory=list)
    changed_fields: list[str] = Field(default_factory=list)


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
            "Structured master/layout/placeholder emission exists "
            "(PptxStructureMode.STRUCTURED + OOXML validation); "
            "FILL_NATIVE still rebuilds via RenderScene and does not yet "
            "clone/preserve an input template's original OOXML master parts in place."
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

    def validate_before(
        self,
        route: PresentationWorkflowRoute,
        available_inputs: set[str] | frozenset[str],
        before: Mapping[str, Any],
    ) -> WorkflowRouteContract:
        """Validate inputs and require a baseline for every preservation promise."""
        contract = self.validate_inputs(route, available_inputs)
        missing = sorted(contract.preserved - before.keys())
        if missing:
            raise WorkflowError(
                f"Workflow route {route.value} cannot establish preservation baseline for: "
                f"{', '.join(missing)}"
            )
        return contract

    def validate_after(
        self,
        route: PresentationWorkflowRoute,
        before: Mapping[str, Any],
        after: Mapping[str, Any],
    ) -> RoutePreservationReport:
        """Fail closed when any field promised by the route changed or disappeared."""
        preserved = self.contract(route).preserved
        missing_before = sorted(preserved - before.keys())
        missing_after = sorted(preserved - after.keys())
        comparable = preserved - set(missing_before) - set(missing_after)
        changed = sorted(field for field in comparable if before[field] != after[field])
        report = RoutePreservationReport(
            route=route,
            valid=not (missing_before or missing_after or changed),
            preserved_fields=preserved,
            missing_before_fields=missing_before,
            missing_after_fields=missing_after,
            changed_fields=changed,
        )
        if not report.valid:
            raise WorkflowError(
                f"Workflow route {route.value} violated preservation contract: "
                f"missing_before={missing_before}, missing_after={missing_after}, "
                f"changed={changed}"
            )
        return report


WorkflowRouteHandler = Callable[[Any], Any]
PreservationSnapshotter = Callable[[Any], Mapping[str, Any]]


class PresentationWorkflowRouter:
    """Dispatch a request to exactly one route handler with preservation gates."""

    def __init__(
        self,
        handlers: Mapping[PresentationWorkflowRoute, WorkflowRouteHandler],
        *,
        snapshotters: Mapping[PresentationWorkflowRoute, PreservationSnapshotter] | None = None,
        route_service: WorkflowRouteService | None = None,
    ) -> None:
        self._handlers = dict(handlers)
        self._snapshotters = dict(snapshotters or {})
        self._routes = route_service or WorkflowRouteService()

    def execute(
        self,
        route: PresentationWorkflowRoute,
        request: Any,
        *,
        available_inputs: set[str] | frozenset[str],
    ) -> Any:
        """Validate, dispatch, then verify the route's preservation promises."""
        handler = self._handlers.get(route)
        if handler is None:
            registration = self._routes.registration(route)
            details = "; ".join(registration.limitations) or "No executable handler is registered."
            raise WorkflowError(f"Workflow route {route.value} has no executable handler: {details}")

        preserved = self._routes.contract(route).preserved
        snapshotter = self._snapshotters.get(route)
        if preserved and snapshotter is None:
            raise WorkflowError(
                f"Workflow route {route.value} has preservation promises but no snapshotter"
            )
        before = dict(snapshotter(request)) if snapshotter is not None else {}
        self._routes.validate_before(route, available_inputs, before)
        result = handler(request)
        after = dict(snapshotter(result)) if snapshotter is not None else {}
        self._routes.validate_after(route, before, after)
        return result
