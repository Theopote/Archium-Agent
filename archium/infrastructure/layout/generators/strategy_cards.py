"""Strategy-cards layout generator."""

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
from archium.infrastructure.layout.geometry import Rect, grid_cells


class StrategyCardsLayoutGenerator(LayoutGenerator):
    family = LayoutFamily.STRATEGY_CARDS

    def generate(self, context: LayoutGeneratorContext) -> LayoutPlan:
        safe = self._safe(context.design_system)
        spacing = context.design_system.spacing
        elements: list[LayoutElement] = []

        card_count = 4 if context.variant == "four_cards" else 3
        points = list(context.content.key_points[:card_count])
        while len(points) < card_count:
            points.append(f"策略 {len(points) + 1}")

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
