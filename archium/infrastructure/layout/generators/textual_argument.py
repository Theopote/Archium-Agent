"""Textual-argument layout generator."""

from __future__ import annotations

from archium.domain.visual.enums import (
    ConstraintPriority,
    LayoutConstraintType,
    LayoutContentType,
    LayoutElementRole,
    LayoutFamily,
)
from archium.domain.visual.layout import LayoutConstraint, LayoutElement, LayoutPlan
from archium.infrastructure.layout.generators.base import LayoutGenerator, LayoutGeneratorContext
from archium.infrastructure.layout.geometry import Rect, split_horizontal


class TextualArgumentLayoutGenerator(LayoutGenerator):
    family = LayoutFamily.TEXTUAL_ARGUMENT

    def generate(self, context: LayoutGeneratorContext) -> LayoutPlan:
        safe = self._safe(context.design_system)
        spacing = context.design_system.spacing
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
            )
        )

        body_top = safe.y + title_h + spacing.md
        body = Rect(safe.x, body_top, safe.width, max(1.0, safe.bottom - body_top - spacing.sm))

        if context.variant == "two_column_text":
            left, right = split_horizontal(body, left_ratio=0.48, gap=spacing.lg)
            elements.append(
                LayoutElement(
                    id="lead",
                    role=LayoutElementRole.LEAD_STATEMENT,
                    content_type=LayoutContentType.TEXT,
                    text_content=context.content.message,
                    x=left.x,
                    y=left.y,
                    width=left.width,
                    height=left.height,
                    style_token="body",
                )
            )
            points = "\n".join(f"· {point}" for point in context.content.key_points) or "· 要点待补充"
            elements.append(
                LayoutElement(
                    id="body",
                    role=LayoutElementRole.BODY_TEXT,
                    content_type=LayoutContentType.TEXT,
                    text_content=points,
                    x=right.x,
                    y=right.y,
                    width=right.width,
                    height=right.height,
                    style_token="body",
                )
            )
        else:
            lead_h = body.height * 0.35
            elements.append(
                LayoutElement(
                    id="lead",
                    role=LayoutElementRole.LEAD_STATEMENT,
                    content_type=LayoutContentType.TEXT,
                    text_content=context.content.message,
                    x=body.x,
                    y=body.y,
                    width=body.width,
                    height=lead_h,
                    style_token="subtitle",
                )
            )
            points = "\n".join(f"· {point}" for point in context.content.key_points) or "· 要点待补充"
            elements.append(
                LayoutElement(
                    id="body",
                    role=LayoutElementRole.BODY_TEXT,
                    content_type=LayoutContentType.TEXT,
                    text_content=points,
                    x=body.x,
                    y=body.y + lead_h + spacing.md,
                    width=body.width * (0.7 if context.content.hero_asset_ref else 1.0),
                    height=max(0.8, body.height - lead_h - spacing.md),
                    style_token="body",
                )
            )

        if context.content.source_text:
            page = context.design_system.page
            elements.append(
                LayoutElement(
                    id="source",
                    role=LayoutElementRole.SOURCE,
                    content_type=LayoutContentType.TEXT,
                    text_content=context.content.source_text,
                    x=safe.x,
                    y=page.height - page.margin_bottom - 0.22,
                    width=safe.width * 0.7,
                    height=0.22,
                    style_token="source",
                )
            )

        constraints = [
            LayoutConstraint(
                constraint_type=LayoutConstraintType.CONTAIN_WITHIN_SAFE_AREA,
                element_ids=[el.id for el in elements],
                priority=ConstraintPriority.REQUIRED,
            ),
            LayoutConstraint(
                constraint_type=LayoutConstraintType.NO_OVERLAP,
                element_ids=[el.id for el in elements],
                priority=ConstraintPriority.REQUIRED,
            ),
            LayoutConstraint(
                constraint_type=LayoutConstraintType.MIN_FONT_SIZE,
                element_ids=["body"],
                value=context.design_system.thresholds.min_body_font_pt,
                priority=ConstraintPriority.REQUIRED,
            ),
        ]
        reading = ["title", "lead", "body"]
        if context.content.source_text:
            reading.append("source")

        return self._build_plan(
            context,
            elements=elements,
            constraints=constraints,
            hero_element_id=None,
            reading_order=reading,
            balance_strategy="text_led",
        )
