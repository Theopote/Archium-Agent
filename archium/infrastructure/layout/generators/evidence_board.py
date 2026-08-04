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
from archium.domain.visual.layout_evidence_item import LayoutEvidenceItem
from archium.infrastructure.layout.generators.base import (
    LayoutGenerator,
    LayoutGeneratorContext,
    resolve_layout_evidence_items,
)
from archium.infrastructure.layout.geometry import (
    Rect,
    grid_cells,
    split_horizontal,
    split_vertical,
)

# Delivery floors for evidence readability (share of safe-area).
_PRIMARY_MIN_SAFE_RATIO = 0.35
_AUX_MIN_SAFE_RATIO = 0.15
_MAX_EVIDENCE_PHOTOS = 3


class PresentationEvidenceBoardLayoutGenerator(LayoutGenerator):
    """Numbered photo evidence board (presentation layout — not IntentEvidence)."""

    family = LayoutFamily.EVIDENCE_BOARD

    def generate(self, context: LayoutGeneratorContext) -> LayoutPlan:
        if context.variant == "diagnosis_split":
            return self._generate_diagnosis_split(context)
        # Default and grid aliases: hierarchical 1+2 + conclusion (not equal 2×2).
        return self._generate_hierarchical(context)

    def _collect_evidence_items(
        self, context: LayoutGeneratorContext, *, limit: int
    ) -> list[LayoutEvidenceItem]:
        return resolve_layout_evidence_items(context.content, limit=limit)

    def _generate_diagnosis_split(self, context: LayoutGeneratorContext) -> LayoutPlan:
        """现状问题页：左主证据、右辅助图+问题标签、底部分析结论。"""
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

        analysis_h = max(safe.height * 0.10, 0.45)
        analysis_h = min(analysis_h, 0.75)
        board_top = safe.y + title_h + spacing.sm
        board_bottom = safe.bottom - analysis_h - spacing.sm
        board = Rect(safe.x, board_top, safe.width, max(1.0, board_bottom - board_top))
        photo_panel, tag_panel = split_horizontal(board, left_ratio=0.62, gap=spacing.lg)

        items = self._collect_evidence_items(context, limit=_MAX_EVIDENCE_PHOTOS)
        count = len(items)

        visual_ids: list[str] = []
        if count == 1:
            cells = [photo_panel]
        elif count == 0:
            cells = []
        else:
            primary, aux_stack = split_horizontal(photo_panel, left_ratio=0.58, gap=spacing.sm)
            if count == 2:
                cells = [primary, aux_stack]
            else:
                aux1, aux2 = split_vertical(aux_stack, top_ratio=0.5, gap=spacing.sm)
                cells = [primary, aux1, aux2]

        for index, (cell, item) in enumerate(zip(cells, items, strict=False)):
            vid = f"photo_{index}"
            visual_ids.append(vid)
            photo_area, caption_area = split_vertical(cell, top_ratio=0.82, gap=spacing.xs)
            elements.append(
                LayoutElement(
                    id=vid,
                    role=LayoutElementRole.SUPPORTING_VISUAL,
                    content_type=LayoutContentType.IMAGE,
                    content_ref=item.asset,
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
                    text_content=f"{index + 1}. {item.claim}",
                    x=caption_area.x,
                    y=caption_area.y,
                    width=caption_area.width,
                    height=caption_area.height,
                    style_token="caption",
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
            grid_rows=None,
        )

    def _generate_hierarchical(self, context: LayoutGeneratorContext) -> LayoutPlan:
        """1 primary (~45%) + 2 aux (~25% each) + conclusion bar (~10%)."""
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

        conclusion_h = max(safe.height * 0.10, 0.42)
        board_top = safe.y + title_h + spacing.sm
        board_bottom = safe.bottom - conclusion_h - spacing.sm
        board = Rect(safe.x, board_top, safe.width, max(1.2, board_bottom - board_top))

        items = self._collect_evidence_items(context, limit=_MAX_EVIDENCE_PHOTOS)
        count = len(items)

        # Geometry: primary left ~62% of board width; two aux stacked on the right.
        if count == 1:
            regions = [board]
        elif count == 2:
            primary, aux = split_horizontal(board, left_ratio=0.62, gap=spacing.md)
            regions = [primary, aux]
        elif count >= 3:
            primary, aux_col = split_horizontal(board, left_ratio=0.62, gap=spacing.md)
            aux1, aux2 = split_vertical(aux_col, top_ratio=0.5, gap=spacing.md)
            regions = [primary, aux1, aux2]
        else:
            regions = []

        visual_ids: list[str] = []
        for index, (region, item) in enumerate(zip(regions, items, strict=False)):
            photo_area, caption_area = split_vertical(region, top_ratio=0.82, gap=spacing.xs)
            vid = f"photo_{index}"
            visual_ids.append(vid)
            elements.append(
                LayoutElement(
                    id=vid,
                    role=LayoutElementRole.SUPPORTING_VISUAL,
                    content_type=LayoutContentType.IMAGE,
                    content_ref=item.asset,
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
                    text_content=f"{index + 1}. {item.claim}",
                    x=caption_area.x,
                    y=caption_area.y,
                    width=caption_area.width,
                    height=caption_area.height,
                    style_token="caption",
                )
            )

        elements.append(
            LayoutElement(
                id="lead",
                role=LayoutElementRole.LEAD_STATEMENT,
                content_type=LayoutContentType.TEXT,
                text_content=context.content.message,
                x=safe.x,
                y=safe.bottom - conclusion_h,
                width=safe.width,
                height=conclusion_h,
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
        reading = ["title", *visual_ids, "lead"]
        if context.content.source_text:
            reading.append("source")

        return self._build_plan(
            context,
            elements=elements,
            constraints=constraints,
            hero_element_id=visual_ids[0] if visual_ids else None,
            reading_order=reading,
            balance_strategy="evidence_hierarchy",
            grid_rows=None,
        )

    def _generate_numbered_grid(self, context: LayoutGeneratorContext) -> LayoutPlan:
        """Legacy equal grid — kept for explicit variant callers / tests."""
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

        items = self._collect_evidence_items(context, limit=_MAX_EVIDENCE_PHOTOS)
        count = max(2, min(_MAX_EVIDENCE_PHOTOS, len(items))) if items else 0
        items = items[:count]

        if count == 0:
            cols = 2
            rows = 1
            cells: list = []
        else:
            cols = 2 if count <= 4 else 3
            rows = (count + cols - 1) // cols
            cells = grid_cells(board, rows=rows, cols=cols, gap_x=spacing.md, gap_y=spacing.md)

        visual_ids: list[str] = []
        for index, (cell, item) in enumerate(zip(cells, items, strict=False)):
            photo_area, caption_area = split_vertical(cell, top_ratio=0.78, gap=spacing.xs)
            vid = f"photo_{index}"
            visual_ids.append(vid)
            elements.append(
                LayoutElement(
                    id=vid,
                    role=LayoutElementRole.SUPPORTING_VISUAL,
                    content_type=LayoutContentType.IMAGE,
                    content_ref=item.asset,
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
                    text_content=f"{index + 1}. {item.claim}",
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


# KN-012 legacy alias — prefer PresentationEvidenceBoardLayoutGenerator in new code.
EvidenceBoardLayoutGenerator = PresentationEvidenceBoardLayoutGenerator

# Re-export floors for validators / tests.
EVIDENCE_PRIMARY_MIN_SAFE_RATIO = _PRIMARY_MIN_SAFE_RATIO
EVIDENCE_AUX_MIN_SAFE_RATIO = _AUX_MIN_SAFE_RATIO
EVIDENCE_MAX_PHOTOS = _MAX_EVIDENCE_PHOTOS
