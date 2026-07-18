"""Evidence-board layout generator — numbered photo evidence."""

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


class EvidenceBoardLayoutGenerator(LayoutGenerator):
    family = LayoutFamily.EVIDENCE_BOARD

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

        lead_h = 0.45
        elements.append(
            LayoutElement(
                id="lead",
                role=LayoutElementRole.LEAD_STATEMENT,
                content_type=LayoutContentType.TEXT,
                text_content=context.content.message,
                x=safe.x,
                y=safe.y + title_h + spacing.xs,
                width=safe.width,
                height=lead_h,
                style_token="subtitle",
            )
        )

        board_top = safe.y + title_h + lead_h + spacing.md
        board = Rect(
            safe.x,
            board_top,
            safe.width,
            max(1.2, safe.bottom - board_top - spacing.sm),
        )

        refs = list(context.content.supporting_asset_refs)
        if context.content.hero_asset_ref and context.content.hero_asset_ref not in refs:
            refs = [context.content.hero_asset_ref, *refs]
        refs = refs[:4] or [f"photo_{i}" for i in range(4)]
        count = max(2, min(4, len(refs)))
        refs = refs[:count]

        cols = 2 if count <= 4 else 3
        rows = (count + cols - 1) // cols
        cells = grid_cells(board, rows=rows, cols=cols, gap_x=spacing.md, gap_y=spacing.md)

        labels = context.content.key_points[:count]
        while len(labels) < count:
            labels.append(f"问题节点 {len(labels) + 1}")

        visual_ids: list[str] = []
        for index, (cell, ref, label) in enumerate(zip(cells, refs, labels, strict=False)):
            photo_area, caption_area = split_vertical(cell, top_ratio=0.78, gap=spacing.xs)
            vid = f"photo_{index}"
            visual_ids.append(vid)
            elements.append(
                LayoutElement(
                    id=vid,
                    role=LayoutElementRole.SUPPORTING_VISUAL,
                    content_type=LayoutContentType.IMAGE,
                    content_ref=ref,
                    x=photo_area.x,
                    y=photo_area.y,
                    width=photo_area.width,
                    height=photo_area.height,
                    fit_mode=ImageFit.COVER,
                    crop_policy=CropPolicy.COVER_CROP,
                    style_token="photo",
                )
            )
            elements.append(
                LayoutElement(
                    id=f"annotation_{index}",
                    role=LayoutElementRole.ANNOTATION,
                    content_type=LayoutContentType.TEXT,
                    text_content=f"{index + 1}. {label}",
                    x=caption_area.x,
                    y=caption_area.y,
                    width=caption_area.width,
                    height=caption_area.height,
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
                constraint_type=LayoutConstraintType.EQUAL_WIDTH,
                element_ids=visual_ids,
                priority=ConstraintPriority.HIGH,
            ),
            LayoutConstraint(
                constraint_type=LayoutConstraintType.EQUAL_HEIGHT,
                element_ids=visual_ids,
                priority=ConstraintPriority.HIGH,
            ),
            LayoutConstraint(
                constraint_type=LayoutConstraintType.NO_OVERLAP,
                element_ids=[el.id for el in elements],
                priority=ConstraintPriority.REQUIRED,
            ),
        ]
        reading = ["title", "lead", *visual_ids]
        if context.content.source_text:
            reading.append("source")

        return self._build_plan(
            context,
            elements=elements,
            constraints=constraints,
            hero_element_id=visual_ids[0] if visual_ids else None,
            reading_order=reading,
            balance_strategy="evidence_grid",
            grid_rows=rows,
        )
