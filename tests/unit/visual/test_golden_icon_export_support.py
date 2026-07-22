from __future__ import annotations

from uuid import uuid4

from archium.domain.visual import LayoutElement, LayoutElementRole, LayoutFamily, LayoutPlan
from archium.domain.visual.enums import LayoutContentType
from archium.infrastructure.renderers.pptxgen.layout_plan_adapter import SlideContentBundle
from tests.golden.visual.composition.artifacts import _bundle_with_icon_asset_paths


def test_bundle_with_icon_asset_paths_resolves_bundled_svg() -> None:
    plan = LayoutPlan(
        slide_id=uuid4(),
        layout_family=LayoutFamily.TEXTUAL_ARGUMENT,
        layout_variant="lead_and_points",
        page_width=10,
        page_height=5.625,
        design_system_id=uuid4(),
        visual_intent_id=uuid4(),
        reading_order=["icon_1", "body"],
        elements=[
            LayoutElement(
                id="icon_1",
                role=LayoutElementRole.DECORATION,
                content_type=LayoutContentType.IMAGE,
                content_ref="icon:pedestrian_flow",
                x=0.7,
                y=0.8,
                width=0.3,
                height=0.3,
                style_token="body",
            ),
            LayoutElement(
                id="body",
                role=LayoutElementRole.BODY_TEXT,
                content_type=LayoutContentType.TEXT,
                text_content="text",
                x=1.1,
                y=0.8,
                width=5,
                height=1,
                style_token="body",
            ),
        ],
    )
    bundle = _bundle_with_icon_asset_paths(plan, SlideContentBundle(page_number=1))
    resolved = bundle.asset_paths.get("icon:pedestrian_flow")
    assert resolved is not None
    assert resolved.endswith(".svg")


def test_bundle_with_icon_asset_paths_keeps_existing_paths() -> None:
    plan = LayoutPlan(
        slide_id=uuid4(),
        layout_family=LayoutFamily.TEXTUAL_ARGUMENT,
        layout_variant="lead_and_points",
        page_width=10,
        page_height=5.625,
        design_system_id=uuid4(),
        visual_intent_id=uuid4(),
        reading_order=["icon_1"],
        elements=[
            LayoutElement(
                id="icon_1",
                role=LayoutElementRole.DECORATION,
                content_type=LayoutContentType.IMAGE,
                content_ref="icon:pedestrian_flow",
                x=0.7,
                y=0.8,
                width=0.3,
                height=0.3,
                style_token="body",
            )
        ],
    )
    bundle = _bundle_with_icon_asset_paths(
        plan,
        SlideContentBundle(
            asset_paths={"icon:pedestrian_flow": "C:/custom/icon.svg"},
            page_number=1,
        ),
    )
    assert bundle.asset_paths["icon:pedestrian_flow"] == "C:/custom/icon.svg"
