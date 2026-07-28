"""GroupNode export / closure: structural only until native grpSp."""

from __future__ import annotations

from uuid import uuid4

from archium.domain.powerpoint_capability import (
    PowerPointDepthStatus,
    PowerPointFidelity,
    assess_scene_node,
    depth_entry,
)
from archium.domain.powerpoint_contract import PowerPointContractService
from archium.domain.visual.render_scene import (
    BackgroundStyle,
    GroupNode,
    RenderScene,
    ShapeNode,
    TextNode,
)
from archium.infrastructure.renderers.scene_pptx_adapter import RenderScenePptxAdapter


def _scene() -> RenderScene:
    return RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=10,
        page_height=5.625,
        background=BackgroundStyle(color="#FFFFFF"),
        nodes=[
            TextNode(
                id="title",
                x=0.5,
                y=0.5,
                width=3,
                height=0.5,
                text="标题",
                font_family="Arial",
                font_size=18,
                color="#111111",
                line_height=1.2,
                group_id="g1",
            ),
            ShapeNode(
                id="badge",
                x=4,
                y=0.5,
                width=1,
                height=0.5,
                fill_color="#EEEEEE",
                group_id="g1",
            ),
            GroupNode(
                id="g1",
                x=0.5,
                y=0.5,
                width=4.5,
                height=0.5,
                children=["title", "badge"],
            ),
        ],
    )


def test_group_depth_is_partial() -> None:
    assert depth_entry("group").status is PowerPointDepthStatus.PARTIAL


def test_group_assessment_is_approximate() -> None:
    scene = _scene()
    group = scene.node_by_id("g1")
    assert group is not None
    assessment = assess_scene_node(group)
    assert assessment.mapping.fidelity is PowerPointFidelity.APPROXIMATE
    assert "children:2" in assessment.detected_features


def test_plan_emissions_skips_group_node_and_closure_passes() -> None:
    scene = _scene()
    contracts = PowerPointContractService()
    emissions = contracts.plan_emissions(scene)
    emitted_sources = {item.source_scene_node_id for item in emissions}
    assert "g1" not in emitted_sources
    assert "title" in emitted_sources
    assert "badge" in emitted_sources
    report = contracts.validate_scene_closure(scene, emissions)
    assert report.valid, (
        f"missing={report.missing_node_ids} "
        f"cardinality={report.cardinality_violations}"
    )


def test_adapter_emits_group_instruction_and_child_group_id() -> None:
    scene = _scene()
    instruction = RenderScenePptxAdapter().render_slide(scene)
    by_id = {item["id"]: item for item in instruction.elements}
    assert by_id["g1"]["content_type"] == "group"
    assert by_id["g1"]["children"] == ["title", "badge"]
    assert by_id["title"]["group_id"] == "g1"
    assert by_id["badge"]["group_id"] == "g1"
