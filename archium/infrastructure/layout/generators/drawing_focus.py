"""Drawing-focus layout generator — technical drawings as hero."""

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


class DrawingFocusLayoutGenerator(LayoutGenerator):
    family = LayoutFamily.DRAWING_FOCUS

    def generate(self, context: LayoutGeneratorContext) -> LayoutPlan:
        safe = self._safe(context.design_system)
        spacing = context.design_system.spacing
        variant = context.variant
        elements: list[LayoutElement] = []

        title_h = self._title_band_height(context)
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

        caption_h = 0.28
        source_h = 0.22
        footer_reserve = caption_h + source_h + spacing.sm
        body_top = safe.y + title_h + spacing.sm
        body_h = max(1.0, safe.bottom - body_top - footer_reserve)

        metrics = context.content.metrics[:3] or [
            point for point in context.content.key_points[:3]
        ]

        if variant == "full_canvas" or not metrics:
            drawing = Rect(safe.x, body_top, safe.width, body_h)
            side: Rect | None = None
        else:
            drawing, side = split_horizontal(
                Rect(safe.x, body_top, safe.width, body_h),
                left_ratio=0.72,
                gap=spacing.lg,
            )

        elements.append(
            LayoutElement(
                id="hero",
                role=LayoutElementRole.HERO_VISUAL,
                content_type=LayoutContentType.DRAWING,
                content_ref=context.content.hero_asset_ref,
                x=drawing.x,
                y=drawing.y,
                width=drawing.width,
                height=drawing.height,
                fit_mode=ImageFit.CONTAIN,
                crop_policy=CropPolicy.FORBIDDEN,
                style_token="drawing",
                locked=True,
            )
        )

        if side is not None and metrics:
            metric_h = (side.height - spacing.sm * (len(metrics) - 1)) / len(metrics)
            for index, metric in enumerate(metrics):
                y = side.y + index * (metric_h + spacing.sm)
                elements.append(
                    LayoutElement(
                        id=f"metric_{index}",
                        role=LayoutElementRole.METRIC,
                        content_type=LayoutContentType.METRIC,
                        text_content=metric,
                        x=side.x,
                        y=y,
                        width=side.width,
                        height=metric_h,
                        style_token="metric",
                        alignment="left",
                    )
                )
            if variant == "drawing_with_details" and context.content.key_points:
                # Replace last metric slot already handled; add body below metrics if room.
                pass

        caption_text = (
            context.content.captions[0]
            if context.content.captions
            else context.content.message[:80]
        )
        elements.append(
            LayoutElement(
                id="caption",
                role=LayoutElementRole.CAPTION,
                content_type=LayoutContentType.TEXT,
                text_content=caption_text,
                x=safe.x,
                y=safe.bottom - footer_reserve + spacing.xs,
                width=safe.width * 0.65,
                height=caption_h,
                style_token="caption",
            )
        )
        source = context.content.source_text or "来源待确认"
        elements.append(
            LayoutElement(
                id="source",
                role=LayoutElementRole.SOURCE,
                content_type=LayoutContentType.TEXT,
                text_content=source,
                x=safe.x,
                y=safe.bottom - source_h,
                width=safe.width * 0.65,
                height=source_h,
                style_token="source",
            )
        )

        metric_ids = [el.id for el in elements if el.role == LayoutElementRole.METRIC]
        constraints = [
            LayoutConstraint(
                constraint_type=LayoutConstraintType.CONTAIN_WITHIN_SAFE_AREA,
                element_ids=[el.id for el in elements],
                priority=ConstraintPriority.REQUIRED,
            ),
            LayoutConstraint(
                constraint_type=LayoutConstraintType.PRESERVE_ASPECT_RATIO,
                element_ids=["hero"],
                priority=ConstraintPriority.REQUIRED,
            ),
            LayoutConstraint(
                constraint_type=LayoutConstraintType.NO_OVERLAP,
                element_ids=[el.id for el in elements],
                priority=ConstraintPriority.REQUIRED,
            ),
        ]
        if len(metric_ids) >= 2:
            constraints.append(
                LayoutConstraint(
                    constraint_type=LayoutConstraintType.EQUAL_WIDTH,
                    element_ids=metric_ids,
                    priority=ConstraintPriority.HIGH,
                )
            )
            constraints.append(
                LayoutConstraint(
                    constraint_type=LayoutConstraintType.ALIGN_LEFT,
                    element_ids=metric_ids,
                    priority=ConstraintPriority.HIGH,
                )
            )

        reading = ["title", "hero", *metric_ids, "caption", "source"]
        return self._build_plan(
            context,
            elements=elements,
            constraints=constraints,
            hero_element_id="hero",
            reading_order=reading,
            balance_strategy="drawing_dominant",
        )
