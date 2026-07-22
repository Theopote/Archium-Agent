"""Enforce presentation workflow boundaries before side effects begin."""

from __future__ import annotations

from archium.domain.workflow_route import (
    PresentationWorkflowRoute,
    WorkflowRouteContract,
    contract_for_route,
)
from archium.exceptions import WorkflowError


class WorkflowRouteService:
    """Validate route inputs and prevent accidental cross-route execution."""

    def contract(self, route: PresentationWorkflowRoute) -> WorkflowRouteContract:
        return contract_for_route(route)

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

