from uuid import uuid4

import pytest
from archium.application.powerpoint_contract_service import (
    PowerPointContractService,
    RendererEmission,
)
from archium.domain.powerpoint_capability import PowerPointFidelity, capability_for_scene_node
from archium.domain.visual.render_scene import BackgroundStyle, RenderScene, ShapeNode, TextNode
from archium.domain.workflow_route import PresentationWorkflowRoute, contract_for_route
from archium.infrastructure.renderers.scene_pptx_adapter import RenderScenePptxAdapter


def _scene() -> RenderScene:
    return RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=13.333,
        page_height=7.5,
        background=BackgroundStyle(color="#ffffff"),
        nodes=[
            TextNode(
                id="title", x=1, y=1, width=5, height=1, text="Title",
                font_family="Arial", font_size=24, color="#111111", line_height=1.2,
            ),
            ShapeNode(id="accent", x=1, y=2, width=2, height=0.2, visible=False),
        ],
    )


def test_v1_capability_registry_is_explicit_and_fails_closed() -> None:
    assert capability_for_scene_node("text").fidelity == PowerPointFidelity.NATIVE_STABLE
    with pytest.raises(ValueError, match="No PowerPoint capability mapping"):
        capability_for_scene_node("smartart")


def test_beautify_route_locks_semantic_content() -> None:
    contract = contract_for_route(PresentationWorkflowRoute.BEAUTIFY_EXISTING_DECK)
    assert {"page_count", "page_order", "wording", "citations"} <= contract.preserved
    assert contract.mutable == {"layout_plan", "render_scene"}


def test_scene_closure_rejects_renderer_created_visible_content() -> None:
    report = PowerPointContractService().validate_scene_closure(
        _scene(),
        [
            RendererEmission(
                emission_id="title-shape",
                source_scene_node_id="title",
                pptx_object_type="p:sp",
            ),
            RendererEmission(
                emission_id="decoration-shape",
                source_scene_node_id="renderer-decoration",
                pptx_object_type="p:sp",
            ),
        ],
    )
    assert not report.valid
    assert report.unexpected_node_ids == ["renderer-decoration"]


def test_scene_closure_counts_only_visible_authored_nodes() -> None:
    service = PowerPointContractService()
    emissions = [
        RendererEmission(
            emission_id="title-shape",
            source_scene_node_id="title",
            pptx_object_type="p:sp",
        )
    ]
    assert service.validate_scene_closure(_scene(), emissions).valid
    service.require_scene_closure(_scene(), emissions)


def test_scene_adapter_does_not_emit_hidden_authored_nodes() -> None:
    instruction = RenderScenePptxAdapter().render_slide(_scene())
    assert [element['id'] for element in instruction.elements] == ['title']
