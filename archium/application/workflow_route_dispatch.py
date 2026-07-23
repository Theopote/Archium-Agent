"""Executable handlers for PresentationWorkflowRouter composition roots."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from pydantic import Field

from archium.application.workflow_route_service import (
    PresentationWorkflowRouter,
    PreservationSnapshotter,
    WorkflowRouteHandler,
    WorkflowRouteService,
    build_presentation_workflow_router,
)
from archium.domain._base import DomainModel
from archium.domain.asset import Asset
from archium.domain.slide import SlideSpec
from archium.domain.visual.architectural_content_schema import ArchitecturalContentSchema
from archium.domain.visual.architectural_template import ArchitecturalTemplate
from archium.domain.visual.design_system import DesignSystem
from archium.domain.visual.reference_slide import ReferenceSlideSnapshot
from archium.domain.visual.reference_slide_editing import ReferenceSlideEditResult
from archium.domain.visual.render_scene import RenderScene
from archium.domain.workflow_route import PresentationWorkflowRoute
from archium.exceptions import WorkflowError


class FillNativeTemplateRequest(DomainModel):
    """Inputs for FILL_NATIVE_TEMPLATE route dispatch."""

    reference_slide: ReferenceSlideSnapshot
    content_schema: ArchitecturalContentSchema
    slide_spec: SlideSpec
    assets: list[Asset] = Field(default_factory=list)
    design_system: DesignSystem
    template: ArchitecturalTemplate
    layout_id: str | None = None
    presentation_id: UUID | None = None
    master_fingerprint: str = ""
    layout_fingerprint: str = ""
    placeholder_fingerprint: str = ""
    theme_fingerprint: str = ""


class FillNativeTemplateResult(DomainModel):
    """Handler result that still carries preservation fingerprints."""

    edit_result: ReferenceSlideEditResult
    scene: RenderScene
    master_fingerprint: str = ""
    layout_fingerprint: str = ""
    placeholder_fingerprint: str = ""
    theme_fingerprint: str = ""


def fill_native_preservation_snapshot(
    payload: FillNativeTemplateRequest | FillNativeTemplateResult | Mapping[str, Any],
) -> dict[str, Any]:
    if isinstance(payload, Mapping):
        return {
            "master": payload.get("master_fingerprint", ""),
            "layout": payload.get("layout_fingerprint", ""),
            "placeholder": payload.get("placeholder_fingerprint", ""),
            "theme": payload.get("theme_fingerprint", ""),
        }
    return {
        "master": payload.master_fingerprint,
        "layout": payload.layout_fingerprint,
        "placeholder": payload.placeholder_fingerprint,
        "theme": payload.theme_fingerprint,
    }


def structure_fingerprints_from_template(
    template: ArchitecturalTemplate,
    *,
    layout_id: str | None = None,
) -> dict[str, str]:
    """Stable fingerprints for FILL_NATIVE preservation checks."""
    layout_ids = tuple(sorted(str(layout.id) for layout in template.layouts))
    selected = layout_id or (layout_ids[0] if layout_ids else "")
    placeholders: list[str] = []
    for layout in template.layouts:
        for slot in getattr(layout, "slots", []) or []:
            placeholders.append(f"{layout.id}:{getattr(slot, 'id', '')}")
    design_id = str(template.design_system_id) if template.design_system_id else ""
    return {
        "master_fingerprint": f"template:{template.id}:masters:{len(layout_ids)}",
        "layout_fingerprint": f"template:{template.id}:layout:{selected}:all:{','.join(layout_ids)}",
        "placeholder_fingerprint": f"template:{template.id}:ph:{','.join(sorted(placeholders))}",
        "theme_fingerprint": f"design:{design_id}:colors:{len(template.colors)}",
    }


@dataclass(frozen=True)
class GenerateFromProjectRequest:
    project_id: UUID
    payload: Any


def build_default_workflow_router(
    *,
    generate_handler: WorkflowRouteHandler | None = None,
    fill_handler: WorkflowRouteHandler | None = None,
    recover_handler: WorkflowRouteHandler | None = None,
    distill_handler: WorkflowRouteHandler | None = None,
    route_service: WorkflowRouteService | None = None,
) -> PresentationWorkflowRouter:
    """Compose the production dispatch map for executable routes.

    Planned routes (Beautify / Enhance) are intentionally omitted until handlers
    and snapshotters exist. FILL_NATIVE remains Partial in availability but is
    dispatchable when ``fill_handler`` is provided.
    """
    handlers: dict[PresentationWorkflowRoute, WorkflowRouteHandler] = {}
    snapshotters: dict[PresentationWorkflowRoute, PreservationSnapshotter] = {}

    if generate_handler is not None:
        handlers[PresentationWorkflowRoute.GENERATE_FROM_PROJECT] = generate_handler
    if fill_handler is not None:
        handlers[PresentationWorkflowRoute.FILL_NATIVE_TEMPLATE] = fill_handler
        snapshotters[PresentationWorkflowRoute.FILL_NATIVE_TEMPLATE] = (
            fill_native_preservation_snapshot
        )
    if recover_handler is not None:
        handlers[PresentationWorkflowRoute.RECOVER_IMAGE_DECK] = recover_handler
        snapshotters[PresentationWorkflowRoute.RECOVER_IMAGE_DECK] = (
            lambda payload: {"visual_appearance": _attr(payload, "visual_appearance", "")}
        )
    if distill_handler is not None:
        handlers[PresentationWorkflowRoute.DISTILL_TEMPLATE] = distill_handler
        snapshotters[PresentationWorkflowRoute.DISTILL_TEMPLATE] = (
            lambda payload: {"source_provenance": _attr(payload, "source_provenance", "")}
        )

    return build_presentation_workflow_router(
        handlers,
        snapshotters=snapshotters,
        route_service=route_service,
    )


def make_fill_native_handler(
    generate_scene: Callable[..., ReferenceSlideEditResult],
) -> WorkflowRouteHandler:
    """Wrap ReferenceSlideEditingService.generate_scene for router dispatch."""

    def _handler(request: FillNativeTemplateRequest) -> FillNativeTemplateResult:
        if not isinstance(request, FillNativeTemplateRequest):
            raise WorkflowError("FILL_NATIVE_TEMPLATE requires FillNativeTemplateRequest")
        fingerprints = {
            "master_fingerprint": request.master_fingerprint,
            "layout_fingerprint": request.layout_fingerprint,
            "placeholder_fingerprint": request.placeholder_fingerprint,
            "theme_fingerprint": request.theme_fingerprint,
        }
        if not all(fingerprints.values()):
            fingerprints = {
                **structure_fingerprints_from_template(
                    request.template, layout_id=request.layout_id
                ),
                **{key: value for key, value in fingerprints.items() if value},
            }
        edit_result = generate_scene(
            reference_slide=request.reference_slide,
            content_schema=request.content_schema,
            slide_spec=request.slide_spec,
            assets=request.assets,
            design_system=request.design_system,
            template=request.template,
            layout_id=request.layout_id,
            presentation_id=request.presentation_id,
        )
        return FillNativeTemplateResult(
            edit_result=edit_result,
            scene=edit_result.scene,
            master_fingerprint=str(fingerprints["master_fingerprint"]),
            layout_fingerprint=str(fingerprints["layout_fingerprint"]),
            placeholder_fingerprint=str(fingerprints["placeholder_fingerprint"]),
            theme_fingerprint=str(fingerprints["theme_fingerprint"]),
        )

    return _handler


def execute_fill_native_template(
    request: FillNativeTemplateRequest,
    *,
    generate_scene: Callable[..., ReferenceSlideEditResult],
    route_service: WorkflowRouteService | None = None,
    available_inputs: set[str] | frozenset[str] | None = None,
) -> FillNativeTemplateResult:
    """Production entry: validate → snapshot → fill handler → preservation check."""
    router = build_default_workflow_router(
        fill_handler=make_fill_native_handler(generate_scene),
        route_service=route_service,
    )
    inputs = available_inputs or {"native_template", "project_knowledge"}
    result = router.execute(
        PresentationWorkflowRoute.FILL_NATIVE_TEMPLATE,
        request,
        available_inputs=inputs,
    )
    if not isinstance(result, FillNativeTemplateResult):
        raise WorkflowError("FILL_NATIVE_TEMPLATE handler returned unexpected result")
    return result


def _attr(payload: Any, name: str, default: Any) -> Any:
    if isinstance(payload, Mapping):
        return payload.get(name, default)
    return getattr(payload, name, default)
