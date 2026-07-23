"""Workflow route dispatch composition — real handlers + preservation."""

from __future__ import annotations

from uuid import uuid4

import pytest
from archium.application.workflow_route_dispatch import (
    FillNativeTemplateRequest,
    FillNativeTemplateResult,
    build_default_workflow_router,
    execute_fill_native_template,
    make_fill_native_handler,
    structure_fingerprints_from_template,
)
from archium.domain.visual.architectural_template import ArchitecturalTemplate
from archium.domain.visual.reference_slide_editing import ReferenceSlideEditResult
from archium.domain.visual.render_scene import BackgroundStyle, RenderScene, TextNode
from archium.domain.workflow_route import PresentationWorkflowRoute
from archium.exceptions import WorkflowError


def _minimal_scene() -> RenderScene:
    return RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=10,
        page_height=5.625,
        background=BackgroundStyle(color="#FFFFFF"),
        nodes=[
            TextNode(
                id="t1",
                x=0.5,
                y=0.5,
                width=4,
                height=0.5,
                text="Hello",
                font_family="Arial",
                font_size=18,
                color="#111111",
                line_height=1.2,
            )
        ],
    )


def _request(**overrides: object) -> FillNativeTemplateRequest:
    template = ArchitecturalTemplate(name="T")
    fingerprints = structure_fingerprints_from_template(template)
    payload = {
        "reference_slide": object(),
        "content_schema": object(),
        "slide_spec": object(),
        "design_system": object(),
        "template": template,
        **fingerprints,
        **overrides,
    }
    return FillNativeTemplateRequest.model_construct(**payload)


def test_structure_fingerprints_are_stable_for_template() -> None:
    template = ArchitecturalTemplate(name="T")
    first = structure_fingerprints_from_template(template)
    second = structure_fingerprints_from_template(template)
    assert first == second
    assert first["master_fingerprint"].startswith("template:")


def test_fill_native_handler_echoes_preservation_fingerprints() -> None:
    scene = _minimal_scene()
    edit = ReferenceSlideEditResult(scene=scene, actions=[], warnings=[])
    handler = make_fill_native_handler(lambda **_kwargs: edit)
    request = _request(
        master_fingerprint="m1",
        layout_fingerprint="l1",
        placeholder_fingerprint="p1",
        theme_fingerprint="th1",
    )
    result = handler(request)
    assert result.master_fingerprint == "m1"
    assert result.scene is scene


def test_execute_fill_native_validates_preservation_contract() -> None:
    scene = _minimal_scene()
    edit = ReferenceSlideEditResult(scene=scene, actions=[], warnings=[])
    request = _request()
    result = execute_fill_native_template(request, generate_scene=lambda **_: edit)
    assert result.master_fingerprint == request.master_fingerprint


def test_execute_fill_native_rejects_fingerprint_drift() -> None:
    scene = _minimal_scene()

    def _mutating_generate(request: FillNativeTemplateRequest) -> FillNativeTemplateResult:
        return FillNativeTemplateResult(
            edit_result=ReferenceSlideEditResult(scene=scene, actions=[], warnings=[]),
            scene=scene,
            master_fingerprint="changed",
            layout_fingerprint=request.layout_fingerprint,
            placeholder_fingerprint=request.placeholder_fingerprint,
            theme_fingerprint=request.theme_fingerprint,
        )

    request = _request()
    router = build_default_workflow_router(fill_handler=_mutating_generate)
    with pytest.raises(WorkflowError, match="changed="):
        router.execute(
            PresentationWorkflowRoute.FILL_NATIVE_TEMPLATE,
            request,
            available_inputs={"native_template", "project_knowledge"},
        )
