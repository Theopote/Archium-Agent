"""Strategy-cards layout generator."""

from __future__ import annotations

from archium.domain.visual.enums import (
    ConstraintPriority,
    ImageFit,
    LayoutConstraintType,
    LayoutContentType,
    LayoutElementRole,
    LayoutFamily,
)
from archium.domain.visual.layout import LayoutConstraint, LayoutElement, LayoutPlan
from archium.infrastructure.layout.generators.base import LayoutGenerator, LayoutGeneratorContext
from archium.infrastructure.layout.geometry import Rect, grid_cells, split_horizontal


class StrategyCardsLayoutGenerator(LayoutGenerator):
    family = LayoutFamily.STRATEGY_CARDS

    def generate(self, context: LayoutGeneratorContext) -> LayoutPlan:
        if context.variant == "strategy_concept":
            return self._generate_strategy_concept(context)
        return self._generate_cards(context)

    def _generate_strategy_concept(self, context: LayoutGeneratorContext) -> LayoutPlan:
        """设计策略页：策略关键词卡片 + 概念图 + 空间变化说明。"""
        safe = self._safe(context.design_system)
        spacing = context.design_system.spacing
        elements: list[LayoutElement] = []

        card_count = 3
        keywords = list(context.content.key_points[:card_count])
        while len(keywords) < card_count:
            keywords.append(f"策略 {len(keywords) + 1}")

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

        lead_h = 0.38
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

        cards_top = safe.y + title_h + lead_h + spacing.sm
        cards_h = 0.72
        cards_area = Rect(safe.x, cards_top, safe.width, cards_h)
        cells = grid_cells(cards_area, rows=1, cols=card_count, gap_x=spacing.md, gap_y=0)

        card_ids: list[str] = []
        for index, (cell, keyword) in enumerate(zip(cells, keywords, strict=True)):
            cid = f"card_{index}"
            card_ids.append(cid)
            elements.append(
                LayoutElement(
                    id=cid,
                    role=LayoutElementRole.BODY_TEXT,
                    content_type=LayoutContentType.TEXT,
                    text_content=keyword,
                    x=cell.x,
                    y=cell.y,
                    width=cell.width,
                    height=cell.height,
                    style_token="body",
                    alignment="center",
                )
            )

        concept_top = cards_area.bottom + spacing.md
        spatial_h = 0.55
        concept_h = max(1.0, safe.bottom - concept_top - spatial_h - spacing.sm)
        concept_area = Rect(safe.x, concept_top, safe.width, concept_h)

        if context.content.hero_asset_ref:
            diagram, spatial_area = split_horizontal(
                concept_area, left_ratio=0.62, gap=spacing.lg
            )
            elements.append(
                LayoutElement(
                    id="concept",
                    role=LayoutElementRole.HERO_VISUAL,
                    content_type=LayoutContentType.DRAWING,
                    content_ref=context.content.hero_asset_ref,
                    x=diagram.x,
                    y=diagram.y,
                    width=diagram.width,
                    height=diagram.height,
                    fit_mode=ImageFit.CONTAIN,
                    style_token="drawing",
                )
            )
        else:
            spatial_area = concept_area
            elements.append(
                LayoutElement(
                    id="concept",
                    role=LayoutElementRole.HERO_VISUAL,
                    content_type=LayoutContentType.TEXT,
                    text_content="概念示意",
                    x=concept_area.x,
                    y=concept_area.y,
                    width=concept_area.width * 0.62,
                    height=concept_area.height,
                    style_token="caption",
                    alignment="center",
                )
            )
            spatial_area = Rect(
                concept_area.x + concept_area.width * 0.62 + spacing.lg,
                concept_area.y,
                concept_area.width * 0.38 - spacing.lg,
                concept_area.height,
            )

        spatial_points = context.content.key_points[card_count : card_count + 3]
        spatial_text = (
            "空间变化\n" + "\n".join(f"→ {point}" for point in spatial_points)
            if spatial_points
            else context.content.message
        )
        elements.append(
            LayoutElement(
                id="spatial_change",
                role=LayoutElementRole.BODY_TEXT,
                content_type=LayoutContentType.TEXT,
                text_content=spatial_text,
                x=spatial_area.x,
                y=spatial_area.y,
                width=spatial_area.width,
                height=spatial_area.height,
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
                    width=safe.width * 0.6,
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
                element_ids=card_ids,
                priority=ConstraintPriority.HIGH,
            ),
            LayoutConstraint(
                constraint_type=LayoutConstraintType.NO_OVERLAP,
                element_ids=[el.id for el in elements],
                priority=ConstraintPriority.REQUIRED,
            ),
        ]
        reading = ["title", "lead", *card_ids, "concept", "spatial_change"]
        if context.content.source_text:
            reading.append("source")

        return self._build_plan(
            context,
            elements=elements,
            constraints=constraints,
            hero_element_id="concept",
            reading_order=reading,
            balance_strategy="strategy_concept",
        )

    def _generate_cards(self, context: LayoutGeneratorContext) -> LayoutPlan:
        safe = self._safe(context.design_system)
        spacing = context.design_system.spacing
        elements: list[LayoutElement] = []

        card_count = 4 if context.variant == "four_cards" else 3
        points = list(context.content.key_points[:card_count])
        while len(points) < card_count:
            points.append(f"策略 {len(points) + 1}")

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

        lead_h = 0.4 if context.variant == "cards_with_lead" else 0.0
        if lead_h:
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
        board = Rect(safe.x, board_top, safe.width, max(1.2, safe.bottom - board_top - spacing.sm))
        cells = grid_cells(board, rows=1, cols=card_count, gap_x=spacing.md, gap_y=0)

        card_ids: list[str] = []
        for index, (cell, point) in enumerate(zip(cells, points, strict=True)):
            cid = f"card_{index}"
            card_ids.append(cid)
            elements.append(
                LayoutElement(
                    id=cid,
                    role=LayoutElementRole.BODY_TEXT,
                    content_type=LayoutContentType.TEXT,
                    text_content=point,
                    x=cell.x,
                    y=cell.y,
                    width=cell.width,
                    height=cell.height,
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
                    width=safe.width * 0.6,
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
                element_ids=card_ids,
                priority=ConstraintPriority.HIGH,
            ),
            LayoutConstraint(
                constraint_type=LayoutConstraintType.EQUAL_HEIGHT,
                element_ids=card_ids,
                priority=ConstraintPriority.HIGH,
            ),
            LayoutConstraint(
                constraint_type=LayoutConstraintType.ALIGN_TOP,
                element_ids=card_ids,
                priority=ConstraintPriority.HIGH,
            ),
            LayoutConstraint(
                constraint_type=LayoutConstraintType.NO_OVERLAP,
                element_ids=[el.id for el in elements],
                priority=ConstraintPriority.REQUIRED,
            ),
        ]
        reading = ["title"]
        if lead_h:
            reading.append("lead")
        reading.extend(card_ids)
        if context.content.source_text:
            reading.append("source")

        return self._build_plan(
            context,
            elements=elements,
            constraints=constraints,
            hero_element_id=None,
            reading_order=reading,
            balance_strategy="equal_cards",
        )
