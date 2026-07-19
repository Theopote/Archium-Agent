"""Comparative matrix layout generator — equal-weight case comparison."""

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
from archium.infrastructure.layout.geometry import Rect, grid_cells, split_vertical


class ComparativeMatrixLayoutGenerator(LayoutGenerator):
    family = LayoutFamily.COMPARATIVE_MATRIX

    def generate(self, context: LayoutGeneratorContext) -> LayoutPlan:
        safe = self._safe(context.design_system)
        spacing = context.design_system.spacing
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

        insight = context.content.insight or context.content.message
        insight_h = 0.55
        cases = 3
        refs = list(context.content.supporting_asset_refs)
        if context.content.hero_asset_ref:
            refs = [context.content.hero_asset_ref, *refs]
        while len(refs) < cases:
            refs.append(f"case_{len(refs)}")
        refs = refs[:cases]

        labels = context.content.case_labels[:cases]
        while len(labels) < cases:
            labels.append(f"案例 {len(labels) + 1}")

        dimensions = context.content.comparison_dimensions[:3] or context.content.key_points[:3]
        while len(dimensions) < 3:
            dimensions.append(f"比较维度 {len(dimensions) + 1}")

        matrix_top = safe.y + title_h + spacing.sm
        matrix = Rect(
            safe.x,
            matrix_top,
            safe.width,
            max(1.5, safe.bottom - matrix_top - insight_h - spacing.md),
        )
        cells = grid_cells(matrix, rows=1, cols=cases, gap_x=spacing.md, gap_y=0)

        visual_ids: list[str] = []
        for index, (cell, ref, label) in enumerate(zip(cells, refs, labels, strict=True)):
            image_area, text_area = split_vertical(cell, top_ratio=0.55, gap=spacing.xs)
            vid = f"case_image_{index}"
            visual_ids.append(vid)
            elements.append(
                LayoutElement(
                    id=vid,
                    role=LayoutElementRole.SUPPORTING_VISUAL,
                    content_type=LayoutContentType.IMAGE,
                    content_ref=ref,
                    x=image_area.x,
                    y=image_area.y,
                    width=image_area.width,
                    height=image_area.height,
                    fit_mode=ImageFit.COVER,
                    crop_policy=CropPolicy.COVER_CROP,
                    style_token="photo",
                )
            )
            dim_text = "\n".join(f"· {dim}" for dim in dimensions)
            elements.append(
                LayoutElement(
                    id=f"case_text_{index}",
                    role=LayoutElementRole.BODY_TEXT,
                    content_type=LayoutContentType.TEXT,
                    text_content=f"{label}\n{dim_text}",
                    x=text_area.x,
                    y=text_area.y,
                    width=text_area.width,
                    height=text_area.height,
                    style_token="body",
                )
            )

        elements.append(
            LayoutElement(
                id="insight",
                role=LayoutElementRole.LEAD_STATEMENT,
                content_type=LayoutContentType.TEXT,
                text_content=insight,
                x=safe.x,
                y=safe.bottom - insight_h,
                width=safe.width,
                height=insight_h,
                style_token="subtitle",
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

        text_ids = [f"case_text_{i}" for i in range(cases)]
        constraints = [
            LayoutConstraint(
                constraint_type=LayoutConstraintType.CONTAIN_WITHIN_SAFE_AREA,
                element_ids=[el.id for el in elements],
                priority=ConstraintPriority.REQUIRED,
            ),
            LayoutConstraint(
                constraint_type=LayoutConstraintType.EQUAL_WIDTH,
                element_ids=visual_ids,
                priority=ConstraintPriority.REQUIRED,
            ),
            LayoutConstraint(
                constraint_type=LayoutConstraintType.EQUAL_HEIGHT,
                element_ids=visual_ids,
                priority=ConstraintPriority.REQUIRED,
            ),
            LayoutConstraint(
                constraint_type=LayoutConstraintType.ALIGN_TOP,
                element_ids=visual_ids,
                priority=ConstraintPriority.HIGH,
            ),
            LayoutConstraint(
                constraint_type=LayoutConstraintType.EQUAL_WIDTH,
                element_ids=text_ids,
                priority=ConstraintPriority.HIGH,
            ),
            LayoutConstraint(
                constraint_type=LayoutConstraintType.NO_OVERLAP,
                element_ids=[el.id for el in elements],
                priority=ConstraintPriority.REQUIRED,
            ),
        ]
        reading = ["title", *visual_ids, *text_ids, "insight"]
        if context.content.source_text:
            reading.append("source")

        return self._build_plan(
            context,
            elements=elements,
            constraints=constraints,
            hero_element_id=None,
            reading_order=reading,
            balance_strategy="equal_columns",
        )
