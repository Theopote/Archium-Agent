"""Contracts for presentation workflows with different preservation promises."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from archium.domain._base import DomainModel


class PresentationWorkflowRoute(StrEnum):
    GENERATE_FROM_PROJECT = "generate_from_project"
    FILL_NATIVE_TEMPLATE = "fill_native_template"
    BEAUTIFY_EXISTING_DECK = "beautify_existing_deck"
    ENHANCE_NATIVE_DECK = "enhance_native_deck"
    RECOVER_IMAGE_DECK = "recover_image_deck"
    DISTILL_TEMPLATE = "distill_template"


class WorkflowRouteContract(DomainModel):
    route: PresentationWorkflowRoute
    preserved: frozenset[str] = Field(default_factory=frozenset)
    mutable: frozenset[str] = Field(default_factory=frozenset)
    required_inputs: frozenset[str] = Field(default_factory=frozenset)


WORKFLOW_ROUTE_CONTRACTS: dict[PresentationWorkflowRoute, WorkflowRouteContract] = {
    PresentationWorkflowRoute.GENERATE_FROM_PROJECT: WorkflowRouteContract(
        route=PresentationWorkflowRoute.GENERATE_FROM_PROJECT,
        mutable=frozenset({"content", "storyline", "layout", "render_scene"}),
        required_inputs=frozenset({"project_knowledge"}),
    ),
    PresentationWorkflowRoute.FILL_NATIVE_TEMPLATE: WorkflowRouteContract(
        route=PresentationWorkflowRoute.FILL_NATIVE_TEMPLATE,
        preserved=frozenset({"master", "layout", "placeholder", "theme"}),
        mutable=frozenset({"placeholder_content"}),
        required_inputs=frozenset({"native_template", "project_knowledge"}),
    ),
    PresentationWorkflowRoute.BEAUTIFY_EXISTING_DECK: WorkflowRouteContract(
        route=PresentationWorkflowRoute.BEAUTIFY_EXISTING_DECK,
        preserved=frozenset({"page_count", "page_order", "wording", "citations"}),
        mutable=frozenset({"layout_plan", "render_scene"}),
        required_inputs=frozenset({"source_deck"}),
    ),
    PresentationWorkflowRoute.ENHANCE_NATIVE_DECK: WorkflowRouteContract(
        route=PresentationWorkflowRoute.ENHANCE_NATIVE_DECK,
        preserved=frozenset({"content", "layout", "master", "native_objects"}),
        mutable=frozenset({"notes", "narration", "transitions", "timing"}),
        required_inputs=frozenset({"source_deck"}),
    ),
    PresentationWorkflowRoute.RECOVER_IMAGE_DECK: WorkflowRouteContract(
        route=PresentationWorkflowRoute.RECOVER_IMAGE_DECK,
        preserved=frozenset({"visual_appearance"}),
        mutable=frozenset({"recovered_structure", "render_scene"}),
        required_inputs=frozenset({"image_deck"}),
    ),
    PresentationWorkflowRoute.DISTILL_TEMPLATE: WorkflowRouteContract(
        route=PresentationWorkflowRoute.DISTILL_TEMPLATE,
        preserved=frozenset({"source_provenance"}),
        mutable=frozenset({"template_contract"}),
        required_inputs=frozenset({"template_references"}),
    ),
}


def contract_for_route(route: PresentationWorkflowRoute) -> WorkflowRouteContract:
    return WORKFLOW_ROUTE_CONTRACTS[route]

