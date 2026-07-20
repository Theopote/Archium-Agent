"""Unit tests for TemplateLayoutMatcher ranking."""

from __future__ import annotations

from uuid import uuid4

from archium.application.visual.template_layout_matcher import TemplateLayoutMatcher
from archium.domain.asset import Asset
from archium.domain.enums import AssetType, SlideType
from archium.domain.slide import SlideSpec
from archium.domain.visual.architectural_template import (
    ArchitecturalTemplate,
    ArchitecturalTemplateLayout,
    TemplatePageType,
    TemplateSlot,
    TemplateSlotRole,
)
from archium.domain.visual.enums import DensityLevel, LayoutFamily, VisualContentType
from archium.domain.visual.visual_intent import VisualIntent


def _slide() -> SlideSpec:
    return SlideSpec(
        presentation_id=uuid4(),
        title="院区总平面",
        slide_type=SlideType.CONTENT,
        order=0,
        chapter_id="ch1",
        message="展示总平面与核心指标。",
        key_points=["总建筑面积 12 万㎡", "绿化率 35%"],
    )


def _intent(*, content: VisualContentType, families: list[LayoutFamily] | None = None) -> VisualIntent:
    return VisualIntent(
        slide_id=uuid4(),
        communication_goal="突出图纸主视觉",
        audience_takeaway="读懂场地关系",
        visual_priority="drawing",
        dominant_content_type=content,
        preferred_layout_families=families or [LayoutFamily.DRAWING_FOCUS],
        density_level=DensityLevel.BALANCED,
    )


def _template() -> ArchitecturalTemplate:
    drawing = ArchitecturalTemplateLayout(
        name="图纸页",
        page_index=0,
        page_type=TemplatePageType.DRAWING_FOCUS,
        supports_drawing=True,
        minimum_asset_count=1,
        maximum_asset_count=2,
        density_range=(0.3, 0.6),
        slots=[
            TemplateSlot(
                id="title",
                role=TemplateSlotRole.TITLE,
                x=0.7,
                y=0.4,
                width=8.0,
                height=0.6,
            ),
            TemplateSlot(
                id="drawing",
                role=TemplateSlotRole.DRAWING,
                x=0.7,
                y=1.2,
                width=8.5,
                height=3.8,
            ),
        ],
    )
    text = ArchitecturalTemplateLayout(
        name="文字页",
        page_index=1,
        page_type=TemplatePageType.TEXT_ARGUMENT,
        supports_drawing=False,
        minimum_asset_count=0,
        maximum_asset_count=0,
        density_range=(0.2, 0.5),
        slots=[
            TemplateSlot(
                id="title2",
                role=TemplateSlotRole.TITLE,
                x=0.7,
                y=0.4,
                width=8.0,
                height=0.6,
            ),
            TemplateSlot(
                id="body",
                role=TemplateSlotRole.BODY,
                x=0.7,
                y=1.3,
                width=8.0,
                height=3.5,
            ),
        ],
    )
    return ArchitecturalTemplate(
        name="Matcher Fixture",
        layouts=[drawing, text],
        design_system_id=uuid4(),
    )


def test_matcher_ranks_drawing_layout_highest_for_site_plan_intent() -> None:
    template = _template()
    assets = [
        Asset(
            project_id=uuid4(),
            filename="site.png",
            path="site.png",
            asset_type=AssetType.DRAWING,
        )
    ]
    ranked = TemplateLayoutMatcher().rank_layouts(
        slide_spec=_slide(),
        visual_intent=_intent(content=VisualContentType.SITE_PLAN),
        assets=assets,
        template=template,
        limit=3,
    )
    assert ranked
    assert ranked[0].page_type == TemplatePageType.DRAWING_FOCUS.value
    assert ranked[0].score >= ranked[-1].score
    assert any("drawing" in reason for reason in ranked[0].reasons)


def test_matcher_penalizes_drawing_layout_without_assets_for_text_intent() -> None:
    template = _template()
    ranked = TemplateLayoutMatcher().rank_layouts(
        slide_spec=_slide(),
        visual_intent=_intent(
            content=VisualContentType.TEXT_ARGUMENT,
            families=[LayoutFamily.TEXTUAL_ARGUMENT],
        ),
        assets=[],
        template=template,
        limit=3,
    )
    assert ranked
    assert ranked[0].page_type == TemplatePageType.TEXT_ARGUMENT.value
