"""Analytical-diagram layout generator — diagram + legend + conclusions."""

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
from archium.infrastructure.layout.geometry import Rect, split_horizontal, split_vertical


class AnalyticalDiagramLayoutGenerator(LayoutGenerator):
    family = LayoutFamily.ANALYTICAL_DIAGRAM

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

        conclusions = list(context.content.key_points[:3])
        legend_items = list(context.content.captions[:4]) or [
            point for point in context.content.key_points[3:6]
        ]
        use_side = context.variant == "diagram_with_callouts" and (
            bool(conclusions) or bool(legend_items)
        )

        if use_side:
            diagram, side = split_horizontal(body, left_ratio=0.62, gap=spacing.lg)
        else:
            diagram = body
            side = None

        elements.append(
            LayoutElement(
                id="hero",
                role=LayoutElementRole.HERO_VISUAL,
                content_type=LayoutContentType.DRAWING,
                content_ref=context.content.hero_asset_ref,
                x=diagram.x,
                y=diagram.y,
                width=diagram.width,
                height=diagram.height,
                fit_mode=ImageFit.CONTAIN,
                crop_policy=CropPolicy.FORBIDDEN,
                style_token="drawing",
                locked=True,
            )
        )

        side_ids: list[str] = []
        if side is not None:
            has_legend = bool(legend_items)
            has_conclusions = bool(conclusions)
            if has_legend and has_conclusions:
                legend_area, conclusion_area = split_vertical(
                    side, top_ratio=0.38, gap=spacing.sm
                )
            elif has_legend:
                legend_area, conclusion_area = side, None
            else:
                legend_area, conclusion_area = None, side

            if legend_area is not None and legend_items:
                elements.append(
                    LayoutElement(
                        id="legend",
                        role=LayoutElementRole.CAPTION,
                        content_type=LayoutContentType.TEXT,
                        text_content="图例\n" + "\n".join(f"· {item}" for item in legend_items),
                        x=legend_area.x,
                        y=legend_area.y,
                        width=legend_area.width,
                        height=legend_area.height,
                        style_token="caption",
                    )
                )
                side_ids.append("legend")

            if conclusion_area is not None and conclusions:
                row_h = (
                    conclusion_area.height - spacing.xs * (len(conclusions) - 1)
                ) / max(1, len(conclusions))
                for index, text in enumerate(conclusions):
                    cid = f"conclusion_{index}"
                    side_ids.append(cid)
                    elements.append(
                        LayoutElement(
                            id=cid,
                            role=LayoutElementRole.ANNOTATION,
                            content_type=LayoutContentType.TEXT,
                            text_content=f"结论 {index + 1}：{text}",
                            x=conclusion_area.x,
                            y=conclusion_area.y + index * (row_h + spacing.xs),
                            width=conclusion_area.width,
                            height=row_h,
                            style_token="caption",
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
        reading = ["title", "hero", *side_ids]
        if context.content.source_text:
            reading.append("source")

        return self._build_plan(
            context,
            elements=elements,
            constraints=constraints,
            hero_element_id="hero",
            reading_order=reading,
            balance_strategy="diagram_dominant",
        )
