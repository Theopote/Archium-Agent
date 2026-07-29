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
from archium.infrastructure.layout.variant_layout_tokens import compute_hero_split_text_ratio


class HeroLayoutGenerator(LayoutGenerator):
    family = LayoutFamily.HERO

    def generate(self, context: LayoutGeneratorContext) -> LayoutPlan:
        safe = self._safe(context.design_system)
        spacing = context.design_system.spacing
        variant = context.variant
        tokens = self._layout_tokens(context)
        elements: list[LayoutElement] = []

        title_h = self._title_band_height(context)
        title_width = safe.width
        elements.append(
            LayoutElement(
                id="title",
                role=LayoutElementRole.TITLE,
                content_type=LayoutContentType.TEXT,
                text_content=context.content.title,
                x=safe.x,
                y=safe.y,
                width=title_width,
                height=title_h,
                style_token="title",
                z_index=2,
            )
        )

        body = Rect(
            safe.x,
            safe.y + title_h + spacing.xs,
            safe.width,
            max(0.5, safe.bottom - (safe.y + title_h + spacing.xs) - spacing.xs),
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
                y=body.y + body.height * tokens.overlay_lead_y_ratio,
                width=body.width * tokens.overlay_lead_width_ratio,
                height=body.height * tokens.overlay_lead_height_ratio,
                style_token="subtitle",
                z_index=3,
            )
        else:
            # Hero dominates on the left; text is a thin supporting panel — not a
            # right-side postcard card with a large empty text column.
            text_ratio = compute_hero_split_text_ratio(body, tokens, gap=spacing.lg)
            hero_ratio = max(0.55, 1.0 - text_ratio)
            left, right = split_horizontal(body, left_ratio=hero_ratio, gap=spacing.lg)
            hero_rect = left
            lead = LayoutElement(
                id="lead",
                role=LayoutElementRole.LEAD_STATEMENT,
                content_type=LayoutContentType.TEXT,
                text_content=context.content.message,
                x=right.x,
                y=right.y,
                width=right.width,
                height=right.height * tokens.lead_height_ratio,
                style_token="body",
                z_index=2,
            )

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
            source_h = safe.height * tokens.source_max_height_ratio
            elements.append(
                LayoutElement(
                    id="source",
                    role=LayoutElementRole.SOURCE,
                    content_type=LayoutContentType.TEXT,
                    text_content=context.content.source_text,
                    x=safe.x,
                    y=page.height - page.margin_bottom - source_h,
                    width=safe.width * tokens.source_width_ratio,
                    height=source_h,
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
