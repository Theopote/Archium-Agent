from __future__ import annotations

from uuid import uuid4

from archium.application.visual.asset_reference import build_asset_reference_context
from archium.domain.enums import VisualType
from archium.domain.slide import SlideSpec, VisualRequirement
from archium.domain.visual import (
    LayoutElementRole,
    LayoutFamily,
    VisualContentType,
    VisualIntent,
    default_presentation_design_system,
)
from archium.domain.visual.enums import LayoutContentType
from archium.infrastructure.layout.generators.base import LayoutGeneratorContext
from archium.infrastructure.layout.generators.base import LayoutContentBundle
from archium.infrastructure.layout.layout_solver import LayoutSolver


def _base_slide(*, key_points: list[str], visual_requirements: list[VisualRequirement]) -> SlideSpec:
    return SlideSpec(
        presentation_id=uuid4(),
        chapter_id="ch-icon",
        order=0,
        title="title",
        message="message",
        key_points=key_points,
        visual_requirements=visual_requirements,
    )


def _visual_intent(*, slide_id, dominant: VisualContentType) -> VisualIntent:
    return VisualIntent(
        slide_id=slide_id,
        presentation_id=None,
        communication_goal="goal",
        audience_takeaway="takeaway",
        visual_priority="priority",
        dominant_content_type=dominant,
        hero_asset_id=uuid4(),
        supporting_asset_ids=[uuid4(), uuid4(), uuid4()],
        hierarchy=["title", "hero", "source"],
        reading_order=["title", "hero", "source"],
        preferred_layout_families=[LayoutFamily.METRIC_DASHBOARD],
        composition_strategy="strategy",
        image_treatment="photo_cover",
        annotation_strategy="caption",
        background_strategy="surface",
    )


def test_metric_dashboard_inserts_icon_elements() -> None:
    slide = _base_slide(
        key_points=["绿地率 42%", "床位 800", "容积率 1.8"],
        visual_requirements=[
            VisualRequirement(
                type=VisualType.ICON,
                description="icon 1",
                icon_canonical_name="pedestrian_flow",
            ),
            VisualRequirement(
                type=VisualType.ICON,
                description="icon 2",
                icon_canonical_name="accessibility",
            ),
            VisualRequirement(
                type=VisualType.ICON,
                description="icon 3",
                icon_canonical_name="energy_saving",
            ),
        ],
    )
    design = default_presentation_design_system()
    content = LayoutContentBundle(
        title=slide.title,
        message=slide.message,
        key_points=slide.key_points,
        metrics=["绿地率 42%", "床位 800", "容积率 1.8"],
        source_text=None,
        icon_refs=["icon:pedestrian_flow", "icon:accessibility", "icon:energy_saving"],
    )
    intent = _visual_intent(slide_id=slide.id, dominant=VisualContentType.METRICS)
    ctx = LayoutGeneratorContext(
        slide=slide,
        visual_intent=intent,
        art_direction=None,
        design_system=design,
        content=content,
        variant="metric_cards",
    )
    plan = LayoutSolver().generate(LayoutFamily.METRIC_DASHBOARD, ctx)

    icons = [
        el
        for el in plan.elements
        if el.role == LayoutElementRole.DECORATION and el.content_type == LayoutContentType.IMAGE
    ]
    assert len(icons) >= 3
    assert any(el.content_ref == "icon:pedestrian_flow" for el in icons)


def test_process_narrative_inserts_arrow_icons() -> None:
    slide = _base_slide(
        key_points=["步骤一", "步骤二", "步骤三"],
        visual_requirements=[
            VisualRequirement(type=VisualType.TIMELINE, description="phase1"),
            VisualRequirement(
                type=VisualType.ICON,
                description="arrow 1",
                icon_canonical_name="public_transport",
            ),
            VisualRequirement(
                type=VisualType.ICON,
                description="arrow 2",
                icon_canonical_name="parking",
            ),
        ],
    )
    design = default_presentation_design_system()
    content = LayoutContentBundle(
        title=slide.title,
        message=slide.message,
        key_points=slide.key_points,
        source_text=None,
        supporting_asset_refs=["00000000-0000-0000-0000-000000000001", "00000000-0000-0000-0000-000000000002"],
        icon_refs=["icon:public_transport", "icon:parking"],
    )
    intent = _visual_intent(slide_id=slide.id, dominant=VisualContentType.PROCESS)
    ctx = LayoutGeneratorContext(
        slide=slide,
        visual_intent=intent,
        art_direction=None,
        design_system=design,
        content=content,
        variant="steps_horizontal",
    )
    plan = LayoutSolver().generate(LayoutFamily.PROCESS_NARRATIVE, ctx)

    arrow_0 = plan.element_by_id("arrow_0")
    arrow_1 = plan.element_by_id("arrow_1")
    assert arrow_0 is not None and arrow_0.content_type == LayoutContentType.IMAGE
    assert arrow_0.content_ref == "icon:public_transport"
    assert arrow_1 is not None and arrow_1.content_type == LayoutContentType.IMAGE
    assert arrow_1.content_ref == "icon:parking"


def test_asset_reference_resolves_icon_ref_to_svg(db_session, test_settings) -> None:  # type: ignore[no-untyped-def]
    project_id = uuid4()
    ctx = build_asset_reference_context(
        db_session,
        project_id=project_id,
        content_refs=["icon:pedestrian_flow", None],
        settings=test_settings,
    )
    assert "icon:pedestrian_flow" in ctx.known_asset_ids
    resolved = ctx.resolved_paths.get("icon:pedestrian_flow")
    assert resolved is not None
    assert resolved.endswith(".svg")

    # Ensure the path is a real file so layout validation won't mark it unresolved.
    import os

    assert os.path.isfile(resolved)

