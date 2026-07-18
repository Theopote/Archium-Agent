"""Process-narrative layout generator — timeline / horizontal steps."""

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
from archium.infrastructure.layout.geometry import Rect, grid_cells, split_horizontal


class ProcessNarrativeLayoutGenerator(LayoutGenerator):
    family = LayoutFamily.PROCESS_NARRATIVE

    def generate(self, context: LayoutGeneratorContext) -> LayoutPlan:
        safe = self._safe(context.design_system)
        spacing = context.design_system.spacing
        elements: list[LayoutElement] = []

        steps = list(context.content.key_points[:6]) or [
            context.content.message or "步骤一",
            "步骤二",
            "步骤三",
        ]
        step_count = max(2, min(len(steps), 5))
        steps = steps[:step_count]

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

        lead_h = 0.35
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
        source_reserve = 0.28 if context.content.source_text else 0.0
        board = Rect(
            safe.x,
            board_top,
            safe.width,
            max(1.2, safe.bottom - board_top - source_reserve - spacing.xs),
        )

        step_ids: list[str] = []
        if context.variant == "steps_horizontal" or context.content.hero_asset_ref is None:
            cells = grid_cells(board, rows=1, cols=step_count, gap_x=spacing.md, gap_y=0)
            for index, (cell, step) in enumerate(zip(cells, steps, strict=True)):
                sid = f"step_{index}"
                step_ids.append(sid)
                elements.append(
                    LayoutElement(
                        id=sid,
                        role=LayoutElementRole.BODY_TEXT,
                        content_type=LayoutContentType.TEXT,
                        text_content=f"{index + 1}. {step}",
                        x=cell.x,
                        y=cell.y,
                        width=cell.width,
                        height=cell.height,
                        style_token="body",
                    )
                )
        else:
            # timeline: steps on left, optional visual on right
            left, right = split_horizontal(board, left_ratio=0.58, gap=spacing.lg)
            row_h = (left.height - spacing.sm * (step_count - 1)) / step_count
            for index, step in enumerate(steps):
                sid = f"step_{index}"
                step_ids.append(sid)
                y = left.y + index * (row_h + spacing.sm)
                elements.append(
                    LayoutElement(
                        id=sid,
                        role=LayoutElementRole.BODY_TEXT,
                        content_type=LayoutContentType.TEXT,
                        text_content=f"{index + 1}. {step}",
                        x=left.x,
                        y=y,
                        width=left.width,
                        height=row_h,
                        style_token="body",
                    )
                )
            elements.append(
                LayoutElement(
                    id="support",
                    role=LayoutElementRole.SUPPORTING_VISUAL,
                    content_type=LayoutContentType.IMAGE,
                    content_ref=context.content.hero_asset_ref,
                    x=right.x,
                    y=right.y,
                    width=right.width,
                    height=right.height,
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
                constraint_type=LayoutConstraintType.EQUAL_WIDTH,
                element_ids=step_ids,
                priority=ConstraintPriority.MEDIUM,
            ),
        ]
        reading = ["title", "lead", *step_ids]
        if any(el.id == "support" for el in elements):
            reading.append("support")
        if context.content.source_text:
            reading.append("source")

        return self._build_plan(
            context,
            elements=elements,
            constraints=constraints,
            hero_element_id="support" if any(el.id == "support" for el in elements) else None,
            reading_order=reading,
            balance_strategy="sequential_steps",
        )
