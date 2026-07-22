from uuid import uuid4

from archium.application.export_policy_service import ExportPolicyService
from archium.domain.export_fidelity import ExportPolicy
from archium.domain.powerpoint_capability import PowerPointFidelity
from archium.domain.visual.render_scene import BackgroundStyle, RenderScene, ShapeNode, TextNode


def test_manifest_aggregates_visible_node_powerpoint_fidelity() -> None:
    scene = RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=13.333,
        page_height=7.5,
        background=BackgroundStyle(color="#ffffff"),
        nodes=[
            TextNode(
                id="title",
                x=1,
                y=1,
                width=5,
                height=1,
                text="Title",
                font_family="Arial",
                font_size=24,
                color="#111111",
                line_height=1.2,
            ),
            ShapeNode(
                id="ellipse",
                x=1,
                y=2,
                width=2,
                height=1,
                shape_kind="ellipse",
            ),
            ShapeNode(
                id="hidden",
                x=1,
                y=3,
                width=2,
                height=1,
                visible=False,
            ),
        ],
    )
    service = ExportPolicyService()
    slide = service.assess_scene_fidelity(scene)
    manifest = service.build_deck_manifest(
        presentation_id=uuid4(),
        export_format="PPTX",
        policy=ExportPolicy(),
        slide_results=[slide],
    )

    assert slide.powerpoint_capability_counts[PowerPointFidelity.NATIVE_STABLE] == 1
    assert slide.powerpoint_capability_counts[PowerPointFidelity.APPROXIMATE] == 1
    assert sum(slide.powerpoint_capability_counts.values()) == 2
    assert manifest.powerpoint_capability_counts[PowerPointFidelity.APPROXIMATE] == 1
    assert "PowerPoint approximate: 1 objects" in manifest.summary_lines_zh()

