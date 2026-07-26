"""Visual Primitive Engine — DrawSpec materialization tests."""

from __future__ import annotations

from uuid import uuid4

from archium.application.visual.page_direction_service import PageDirectionService
from archium.application.visual.primitive_materializer import (
    materialize_primitives,
    resolve_role_hex,
)
from archium.application.visual.visual_language_apply import apply_visual_language_to_plan
from archium.domain.slide import SlideSpec
from archium.domain.visual.enums import LayoutContentType, LayoutElementRole, LayoutFamily
from archium.domain.visual.layout import LayoutElement, LayoutPlan
from archium.domain.visual.primitives.draw_spec import draw_spec_for
from archium.domain.visual.visual_language import ColorStory
from archium.domain.visual.visual_language.color_story import NAMED_SWATCHES


def _slide(title: str, message: str, *, order: int = 0) -> SlideSpec:
    return SlideSpec(
        presentation_id=uuid4(),
        chapter_id="demo",
        order=order,
        title=title,
        message=message,
        key_points=["要点"],
    )


def test_draw_specs_exist_for_core_primitives() -> None:
    for pid in ("flow_line", "axis_line", "node", "thin_rule", "overlay_map"):
        spec = draw_spec_for(pid)
        assert spec is not None
        assert spec.geometry.type
        assert spec.style.width_pt > 0


def test_resolve_role_hex_uses_color_story() -> None:
    story = ColorStory(
        roles={"existing": "gray", "conflict": "red", "intervention": "renew_green"}
    )
    assert resolve_role_hex(story, "existing") == NAMED_SWATCHES["gray"]
    assert resolve_role_hex(story, "conflict") == NAMED_SWATCHES["red"]
    assert resolve_role_hex(story, "intervention") == NAMED_SWATCHES["renew_green"]


def test_conflict_page_draws_gray_red_green_pack() -> None:
    slide = _slide("流线冲突", "医患流线交叉与洁污混行是当前最大安全风险。")
    direction = PageDirectionService().direct(slide)
    language = direction.visual_language
    assert language is not None
    assert direction.visual_budget is not None
    assert direction.visual_budget.decorative_lines >= 5
    assert language.color_story.roles.get("existing") in {"gray", "stone_gray"}
    assert language.color_story.roles.get("conflict") in {"red", "alert_red"}
    assert language.color_story.roles.get("intervention") == "renew_green"

    plan = LayoutPlan(
        slide_id=slide.id,
        design_system_id=uuid4(),
        visual_intent_id=uuid4(),
        layout_family=LayoutFamily.ANALYTICAL_DIAGRAM,
        layout_variant="default",
        page_width=13.333,
        page_height=7.5,
        elements=[
            LayoutElement(
                id="hero",
                role=LayoutElementRole.HERO_VISUAL,
                content_type=LayoutContentType.IMAGE,
                x=5.0,
                y=1.0,
                width=7.5,
                height=5.0,
            )
        ],
        reading_order=["hero"],
    )
    updated = apply_visual_language_to_plan(
        plan,
        language,
        page_order=5,
        visual_budget=direction.visual_budget,
    )
    draw_ids = [el.id for el in updated.elements if el.id.startswith("vl_draw_")]
    assert any(i.startswith("vl_draw_flow_existing") for i in draw_ids)
    assert any(i.startswith("vl_draw_flow_network") for i in draw_ids)
    assert "vl_draw_node_conflict" in draw_ids

    existing = next(el for el in updated.elements if el.id.startswith("vl_draw_flow_existing"))
    network = next(el for el in updated.elements if el.id.startswith("vl_draw_flow_network"))
    node = next(el for el in updated.elements if el.id == "vl_draw_node_conflict")
    assert existing.fill_color == NAMED_SWATCHES["gray"]
    assert network.fill_color == NAMED_SWATCHES["renew_green"]
    assert node.fill_color == NAMED_SWATCHES["red"]
    assert node.image_mask == "circle"


def test_flow_line_draw_spec_has_bezier_geometry() -> None:
    spec = draw_spec_for("flow_line")
    assert spec is not None
    assert spec.geometry.type.value == "bezier_approx"
    assert spec.geometry.curvature >= 0.3
    assert spec.style.width_pt >= 1.5
    payload = spec.as_dict()
    assert "geometry" in payload and "style" in payload


def test_case_001_conflict_plan_carries_draw_pack() -> None:
    from archium.application.visual.showcase_case_001 import build_case_001_render_bundle

    bundle = build_case_001_render_bundle()
    idx = next(i for i, s in enumerate(bundle.slides) if s.title == "流线冲突")
    plan = bundle.plans[idx]
    draw_ids = [el.id for el in plan.elements if el.id.startswith("vl_draw_")]
    assert any(i.startswith("vl_draw_flow_existing") for i in draw_ids)
    assert any(i.startswith("vl_draw_flow_network") for i in draw_ids)
    assert "vl_draw_node_conflict" in draw_ids

    from archium.domain.visual.visual_budget import VisualBudget

    plan = LayoutPlan(
        slide_id=uuid4(),
        design_system_id=uuid4(),
        visual_intent_id=uuid4(),
        layout_family=LayoutFamily.ANALYTICAL_DIAGRAM,
        layout_variant="default",
        page_width=10,
        page_height=5.625,
        elements=[],
        reading_order=[],
    )
    story = ColorStory(roles={"intervention": "renew_green", "neutral": "axis_line"})
    out = materialize_primitives(
        plan=plan,
        elements=[],
        primitive_ids=["axis_line", "flow_line"],
        color_story=story,
        budget=VisualBudget(decorative_lines=1, icons=0, color_blocks=0),
        metaphor=None,
    )
    drawn = [el for el in out if el.id.startswith("vl_draw_")]
    assert 1 <= len(drawn) <= 2
