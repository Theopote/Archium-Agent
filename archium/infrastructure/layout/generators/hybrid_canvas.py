"""Hybrid-canvas layout generator — title + hero + supporting text/points."""

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


class HybridCanvasLayoutGenerator(LayoutGenerator):
    """Deterministic mixed layout — not freeform LLM coordinates."""

    family = LayoutFamily.HYBRID_CANVAS

    def generate(self, context: LayoutGeneratorContext) -> LayoutPlan:
        safe = self._safe(context.design_system)
        spacing = context.design_system.spacing
        elements: list[LayoutElement] = []

        title_h = 0.5
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

        source_reserve = 0.28 if context.content.source_text else 0.0
        body_top = safe.y + title_h + spacing.sm
        body = Rect(
            safe.x,
            body_top,
            safe.width,
            max(1.2, safe.bottom - body_top - source_reserve),
        )
        left, right = split_horizontal(body, left_ratio=0.55, gap=spacing.lg)

        elements.append(
            LayoutElement(
                id="hero",
                role=LayoutElementRole.HERO_VISUAL,
                content_type=LayoutContentType.IMAGE,
                content_ref=context.content.hero_asset_ref,
                x=left.x,
                y=left.y,
                width=left.width,
                height=left.height,
                fit_mode=ImageFit.COVER,
                crop_policy=CropPolicy.SAFE_TRIM,
                style_token="hero",
            )
        )

        elements.append(
            LayoutElement(
                id="lead",
                role=LayoutElementRole.LEAD_STATEMENT,
                content_type=LayoutContentType.TEXT,
                text_content=context.content.message,
                x=right.x,
                y=right.y,
                width=right.width,
                height=min(0.9, right.height * 0.35),
                style_token="subtitle",
            )
        )

        points = list(context.content.key_points[:4])
        points_text = "\n".join(f"· {point}" for point in points) if points else ""
        if points_text:
            lead_bottom = right.y + min(0.9, right.height * 0.35) + spacing.sm
            elements.append(
                LayoutElement(
                    id="body",
                    role=LayoutElementRole.BODY_TEXT,
                    content_type=LayoutContentType.TEXT,
                    text_content=points_text,
                    x=right.x,
                    y=lead_bottom,
                    width=right.width,
                    height=max(0.6, right.bottom - lead_bottom),
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
        ]
        reading = ["title", "hero", "lead"]
        if any(el.id == "body" for el in elements):
            reading.append("body")
        if context.content.source_text:
            reading.append("source")

        return self._build_plan(
            context,
            elements=elements,
            constraints=constraints,
            hero_element_id="hero",
            reading_order=reading,
            balance_strategy="hybrid_split",
        )
