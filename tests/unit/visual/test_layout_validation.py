"""Tests for LayoutValidationService rule coverage."""

from __future__ import annotations

from uuid import uuid4

from archium.application.visual.layout_validation_service import LayoutValidationService
from archium.domain.visual import (
    LAYOUT_DRAWING_CROPPED,
    LAYOUT_ELEMENT_OUTSIDE_PAGE,
    LAYOUT_ELEMENT_OVERLAP,
    LAYOUT_FONT_TOO_SMALL,
    LAYOUT_HERO_NOT_DOMINANT,
    LAYOUT_IMAGE_DISTORTION,
    LAYOUT_TEXT_OVERFLOW,
    LayoutElement,
    LayoutElementRole,
    LayoutFamily,
    LayoutPlan,
    default_presentation_design_system,
)
from archium.domain.visual.enums import CropPolicy, ImageFit, LayoutContentType


def _base_plan(*elements: LayoutElement, family: LayoutFamily = LayoutFamily.HERO) -> LayoutPlan:
    return LayoutPlan(
        slide_id=uuid4(),
        layout_family=family,
        layout_variant="split",
        page_width=10,
        page_height=5.625,
        hero_element_id="hero" if any(el.id == "hero" for el in elements) else None,
        reading_order=[el.id for el in elements],
        whitespace_ratio=0.3,
        elements=list(elements),
        design_system_id=uuid4(),
        visual_intent_id=uuid4(),
    )


class TestLayoutValidationService:
    def test_outside_page(self) -> None:
        plan = _base_plan(
            LayoutElement(
                id="title",
                role=LayoutElementRole.TITLE,
                content_type=LayoutContentType.TEXT,
                text_content="标题",
                x=9.5,
                y=0.4,
                width=2.0,
                height=0.5,
                style_token="title",
            )
        )
        report = LayoutValidationService().validate(plan, default_presentation_design_system())
        assert report.issues_for(LAYOUT_ELEMENT_OUTSIDE_PAGE)

    def test_overlap(self) -> None:
        plan = _base_plan(
            LayoutElement(
                id="a",
                role=LayoutElementRole.BODY_TEXT,
                content_type=LayoutContentType.TEXT,
                text_content="A",
                x=1,
                y=1,
                width=3,
                height=2,
                style_token="body",
            ),
            LayoutElement(
                id="b",
                role=LayoutElementRole.BODY_TEXT,
                content_type=LayoutContentType.TEXT,
                text_content="B",
                x=2,
                y=1.5,
                width=3,
                height=2,
                style_token="body",
            ),
        )
        report = LayoutValidationService().validate(plan, default_presentation_design_system())
        assert report.issues_for(LAYOUT_ELEMENT_OVERLAP)

    def test_drawing_crop_forbidden(self) -> None:
        plan = _base_plan(
            LayoutElement(
                id="title",
                role=LayoutElementRole.TITLE,
                content_type=LayoutContentType.TEXT,
                text_content="总图",
                x=0.7,
                y=0.45,
                width=8,
                height=0.5,
                style_token="title",
            ),
            LayoutElement(
                id="hero",
                role=LayoutElementRole.HERO_VISUAL,
                content_type=LayoutContentType.DRAWING,
                x=0.7,
                y=1.2,
                width=8,
                height=3.5,
                fit_mode=ImageFit.COVER,
                crop_policy=CropPolicy.COVER_CROP,
            ),
            family=LayoutFamily.DRAWING_FOCUS,
        )
        report = LayoutValidationService().validate(
            plan, default_presentation_design_system(), drawing_hero=True
        )
        assert report.issues_for(LAYOUT_DRAWING_CROPPED)

    def test_image_distortion(self) -> None:
        plan = _base_plan(
            LayoutElement(
                id="hero",
                role=LayoutElementRole.HERO_VISUAL,
                content_type=LayoutContentType.IMAGE,
                x=1,
                y=1,
                width=4,
                height=3,
                fit_mode=ImageFit.FILL,
            )
        )
        report = LayoutValidationService().validate(plan, default_presentation_design_system())
        assert report.issues_for(LAYOUT_IMAGE_DISTORTION)

    def test_text_overflow_and_font(self) -> None:
        design = default_presentation_design_system()
        tiny = design.typography.source.model_copy(update={"font_size": 6})
        design = design.model_copy(
            update={"typography": design.typography.model_copy(update={"source": tiny})}
        )
        plan = _base_plan(
            LayoutElement(
                id="body",
                role=LayoutElementRole.BODY_TEXT,
                content_type=LayoutContentType.TEXT,
                text_content="这是一段非常长的正文" * 40,
                x=0.7,
                y=1.0,
                width=2.0,
                height=0.4,
                style_token="body",
            ),
            LayoutElement(
                id="source",
                role=LayoutElementRole.SOURCE,
                content_type=LayoutContentType.TEXT,
                text_content="来源",
                x=0.7,
                y=5.2,
                width=3,
                height=0.2,
                style_token="source",
            ),
        )
        report = LayoutValidationService().validate(plan, design, require_source=True)
        assert report.issues_for(LAYOUT_TEXT_OVERFLOW)
        assert report.issues_for(LAYOUT_FONT_TOO_SMALL)

    def test_hero_not_dominant(self) -> None:
        plan = _base_plan(
            LayoutElement(
                id="title",
                role=LayoutElementRole.TITLE,
                content_type=LayoutContentType.TEXT,
                text_content="标题",
                x=0.7,
                y=0.45,
                width=8,
                height=0.5,
                style_token="title",
            ),
            LayoutElement(
                id="hero",
                role=LayoutElementRole.HERO_VISUAL,
                content_type=LayoutContentType.DRAWING,
                x=0.7,
                y=1.2,
                width=2.0,
                height=1.0,
                fit_mode=ImageFit.CONTAIN,
                crop_policy=CropPolicy.FORBIDDEN,
            ),
            family=LayoutFamily.DRAWING_FOCUS,
        )
        report = LayoutValidationService().validate(
            plan, default_presentation_design_system(), drawing_hero=True
        )
        assert report.issues_for(LAYOUT_HERO_NOT_DOMINANT)
