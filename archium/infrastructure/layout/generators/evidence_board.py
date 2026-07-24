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
from archium.infrastructure.layout.geometry import (
    Rect,
    grid_cells,
    split_horizontal,
    split_vertical,
)


class EvidenceBoardLayoutGenerator(LayoutGenerator):
    family = LayoutFamily.EVIDENCE_BOARD

    def generate(self, context: LayoutGeneratorContext) -> LayoutPlan:
        if context.variant == "diagnosis_split":
            return self._generate_diagnosis_split(context)
        return self._generate_numbered_grid(context)

    def _generate_diagnosis_split(self, context: LayoutGeneratorContext) -> LayoutPlan:
        """现状问题页：左照片、右问题标签、底部分析结论。"""
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

        analysis_h = self._text_band_height(
            context,
            context.content.message,
            "subtitle",
            box_width_in=safe.width,
            min_height=0.45,
        )
        analysis_h = min(analysis_h, 0.75)
        board_top = safe.y + title_h + spacing.sm
        board_bottom = safe.bottom - analysis_h - spacing.sm
        board = Rect(safe.x, board_top, safe.width, max(1.0, board_bottom - board_top))
        photo_panel, tag_panel = split_horizontal(board, left_ratio=0.58, gap=spacing.lg)

        refs = list(context.content.supporting_asset_refs)
        if context.content.hero_asset_ref and context.content.hero_asset_ref not in refs:
            refs = [context.content.hero_asset_ref, *refs]
        refs = refs[:4] or [f"photo_{i}" for i in range(2)]
        count = max(1, min(4, len(refs)))
        refs = refs[:count]

        cols = 2 if count >= 2 else 1
        rows = (count + cols - 1) // cols
        cells = grid_cells(photo_panel, rows=rows, cols=cols, gap_x=spacing.sm, gap_y=spacing.sm)

        visual_ids: list[str] = []
        for index, (cell, ref) in enumerate(zip(cells, refs, strict=False)):
            vid = f"photo_{index}"
            visual_ids.append(vid)
            elements.append(
                LayoutElement(
                    id=vid,
                    role=LayoutElementRole.SUPPORTING_VISUAL,
                    content_type=LayoutContentType.IMAGE,
                    content_ref=ref,
                    x=cell.x,
                    y=cell.y,
                    width=cell.width,
                    height=cell.height,
                    fit_mode=ImageFit.COVER,
                    crop_policy=CropPolicy.COVER_CROP,
                    style_token="photo",
                )
            )

        tags = context.content.key_points[:6]
        while len(tags) < min(3, max(1, count)):
            tags.append(f"问题 {len(tags) + 1}")
        tag_text = "\n".join(f"{index + 1}. {tag}" for index, tag in enumerate(tags))
        elements.append(
            LayoutElement(
                id="problem_tags",
                role=LayoutElementRole.BODY_TEXT,
                content_type=LayoutContentType.TEXT,
                text_content=tag_text,
                x=tag_panel.x,
                y=tag_panel.y,
                width=tag_panel.width,
                height=tag_panel.height,
                style_token="body",
            )
        )

        elements.append(
            LayoutElement(
                id="analysis",
                role=LayoutElementRole.LEAD_STATEMENT,
                content_type=LayoutContentType.TEXT,
                text_content=context.content.message,
                x=safe.x,
                y=safe.bottom - analysis_h,
                width=safe.width,
                height=analysis_h,
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
        if len(visual_ids) >= 2:
            constraints.append(
                LayoutConstraint(
                    constraint_type=LayoutConstraintType.EQUAL_WIDTH,
                    element_ids=visual_ids,
                    priority=ConstraintPriority.HIGH,
                )
            )

        reading = ["title", *visual_ids, "problem_tags", "analysis"]
        if context.content.source_text:
            reading.append("source")

        return self._build_plan(
            context,
            elements=elements,
            constraints=constraints,
            hero_element_id=visual_ids[0] if visual_ids else None,
            reading_order=reading,
            balance_strategy="diagnosis_split",
            grid_rows=rows,
        )

    def _generate_numbered_grid(self, context: LayoutGeneratorContext) -> LayoutPlan:
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
