"""Metric-dashboard layout generator — metric cards with optional lead."""

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


class MetricDashboardLayoutGenerator(LayoutGenerator):
    family = LayoutFamily.METRIC_DASHBOARD

    def generate(self, context: LayoutGeneratorContext) -> LayoutPlan:
        safe = self._safe(context.design_system)
        spacing = context.design_system.spacing
        elements: list[LayoutElement] = []

        metrics = list(context.content.metrics[:6]) or list(context.content.key_points[:6])
        while len(metrics) < 3:
            metrics.append(f"指标 {len(metrics) + 1}")
        metrics = metrics[:6]
        count = len(metrics)
        cols = 3 if count >= 3 else count
        rows = (count + cols - 1) // cols

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

        lead_h = self._text_band_height(
            context,
            context.content.message,
            "subtitle",
            min_height=0.4,
        )
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

        source_reserve = 0.28 if context.content.source_text else 0.0
        board_top = safe.y + title_h + lead_h + spacing.md
        board = Rect(
            safe.x,
            board_top,
            safe.width,
            max(1.2, safe.bottom - board_top - source_reserve - spacing.xs),
        )

        chart_note = context.variant == "metric_with_chart"
        if chart_note:
            metrics_area, chart_area = split_vertical(board, top_ratio=0.62, gap=spacing.md)
        else:
            metrics_area = board
            chart_area = None

        cells = grid_cells(
            metrics_area,
            rows=rows,
            cols=cols,
            gap_x=spacing.md,
            gap_y=spacing.md,
        )
        metric_ids: list[str] = []
        icon_refs = list(getattr(context.content, "icon_refs", []) or [])
        for index, (cell, metric) in enumerate(zip(cells, metrics, strict=False)):
            mid = f"metric_{index}"
            metric_ids.append(mid)
            elements.append(
                LayoutElement(
                    id=mid,
                    role=LayoutElementRole.METRIC,
                    content_type=LayoutContentType.METRIC,
                    text_content=metric,
                    x=cell.x,
                    y=cell.y,
                    width=cell.width,
                    height=cell.height,
                    style_token="metric",
                    alignment="center",
                )
            )
            # Optional semantic icon: small, top-left, rendered as a decorative image.
            # Using z_index=1 places it above the metric card background/text.
            if index < len(icon_refs):
                icon = icon_refs[index]
                icon_w = max(0.18, cell.width * 0.32)
                icon_h = max(0.16, cell.height * 0.28)
                icon_x = cell.x + cell.width * 0.06
                icon_y = cell.y + cell.height * 0.06
                elements.append(
                    LayoutElement(
                        id=f"{mid}__icon",
                        role=LayoutElementRole.DECORATION,
                        content_type=LayoutContentType.IMAGE,
                        content_ref=icon,
                        x=icon_x,
                        y=icon_y,
                        width=icon_w,
                        height=icon_h,
                        fit_mode=ImageFit.CONTAIN,
                        crop_policy=CropPolicy.FORBIDDEN,
                        style_token="body",
                        z_index=1,
                    )
                )

        if chart_area is not None:
            chart_ref = context.content.hero_asset_ref
            if chart_ref is None and context.content.supporting_asset_refs:
                chart_ref = context.content.supporting_asset_refs[0]
            elements.append(
                LayoutElement(
                    id="chart",
                    role=LayoutElementRole.SUPPORTING_VISUAL,
                    content_type=LayoutContentType.CHART,
                    content_ref=chart_ref,
                    text_content=context.content.insight
                    or context.content.message
                    or "指标趋势示意",
                    x=chart_area.x,
                    y=chart_area.y,
                    width=chart_area.width,
                    height=chart_area.height,
                    fit_mode=ImageFit.CONTAIN if chart_ref else None,
                    crop_policy=CropPolicy.FORBIDDEN if chart_ref else None,
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
                constraint_type=LayoutConstraintType.EQUAL_HEIGHT,
                element_ids=metric_ids,
                priority=ConstraintPriority.HIGH,
            ),
        ]
        reading = ["title", "lead", *metric_ids]
        if chart_area is not None:
            reading.append("chart")
        if context.content.source_text:
            reading.append("source")

        return self._build_plan(
            context,
            elements=elements,
            constraints=constraints,
            hero_element_id=metric_ids[0] if metric_ids else None,
            reading_order=reading,
            balance_strategy="metric_grid",
            grid_rows=rows,
        )
