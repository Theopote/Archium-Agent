"""Hero layout generator."""

from __future__ import annotations

from archium.domain.visual.enums import (
    ConstraintPriority,
    CropPolicy,
    ImageFit,
    LayoutConstraintType,
    LayoutContentType,
    LayoutElementRole,
    LayoutFamily,
)
from archium.domain.visual.layout import LayoutConstraint, LayoutElement, LayoutPlan
from archium.infrastructure.layout.generators.base import LayoutGenerator, LayoutGeneratorContext
from archium.infrastructure.layout.geometry import Rect, split_horizontal


class HeroLayoutGenerator(LayoutGenerator):
    family = LayoutFamily.HERO

    def generate(self, context: LayoutGeneratorContext) -> LayoutPlan:
        safe = self._safe(context.design_system)
        spacing = context.design_system.spacing
        variant = context.variant
        elements: list[LayoutElement] = []

        title_h = 0.55
        elements.append(
            LayoutElement(
                id="title",
                role=LayoutElementRole.TITLE,
                content_type=LayoutContentType.TEXT,
                text_content=context.content.title,
                x=safe.x,
                y=safe.y,
                width=safe.width,
                height=title_h,
                style_token="title",
                z_index=2,
            )
        )

        body = Rect(
            safe.x,
            safe.y + title_h + spacing.md,
            safe.width,
            max(0.5, safe.bottom - (safe.y + title_h + spacing.md) - spacing.sm),
        )
        lead: LayoutElement | None = None

        if variant == "full_bleed":
            hero_rect = body
        elif variant == "overlay":
            hero_rect = body
            lead = LayoutElement(
                id="lead",
                role=LayoutElementRole.LEAD_STATEMENT,
                content_type=LayoutContentType.TEXT,
                text_content=context.content.message,
                x=body.x + spacing.lg,
                y=body.y + body.height * 0.55,
                width=body.width * 0.45,
                height=body.height * 0.35,
                style_token="subtitle",
                z_index=3,
            )
        else:
            left, right = split_horizontal(body, left_ratio=0.42, gap=spacing.lg)
            lead = LayoutElement(
                id="lead",
                role=LayoutElementRole.LEAD_STATEMENT,
                content_type=LayoutContentType.TEXT,
                text_content=context.content.message,
                x=left.x,
                y=left.y,
                width=left.width,
                height=left.height * 0.5,
                style_token="body",
                z_index=2,
            )
            hero_rect = right

        elements.append(
            LayoutElement(
                id="hero",
                role=LayoutElementRole.HERO_VISUAL,
                content_type=LayoutContentType.IMAGE,
                content_ref=context.content.hero_asset_ref,
                x=hero_rect.x,
                y=hero_rect.y,
                width=hero_rect.width,
                height=hero_rect.height,
                fit_mode=ImageFit.COVER,
                crop_policy=CropPolicy.COVER_CROP,
                style_token="hero",
                z_index=1,
            )
        )
        if lead is not None:
            elements.append(lead)

        if context.content.source_text:
            page = context.design_system.page
            elements.append(
                LayoutElement(
                    id="source",
                    role=LayoutElementRole.SOURCE,
                    content_type=LayoutContentType.TEXT,
                    text_content=context.content.source_text,
                    x=safe.x,
                    y=page.height - page.margin_bottom - 0.25,
                    width=safe.width * 0.7,
                    height=0.25,
                    style_token="source",
                    z_index=2,
                )
            )

        constraints = [
            LayoutConstraint(
                constraint_type=LayoutConstraintType.CONTAIN_WITHIN_SAFE_AREA,
                element_ids=[el.id for el in elements],
                priority=ConstraintPriority.REQUIRED,
            ),
            LayoutConstraint(
                constraint_type=LayoutConstraintType.PRESERVE_ASPECT_RATIO,
                element_ids=["hero"],
                priority=ConstraintPriority.MEDIUM,
            ),
        ]
        reading = ["title"]
        if lead is not None:
            reading.append("lead")
        reading.append("hero")
        if context.content.source_text:
            reading.append("source")

        return self._build_plan(
            context,
            elements=elements,
            constraints=constraints,
            hero_element_id="hero",
            reading_order=reading,
            balance_strategy="image_dominant",
        )
