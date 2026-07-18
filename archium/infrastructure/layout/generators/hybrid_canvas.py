"""Hybrid-canvas layout generator — main drawing + supports + metrics + copy."""

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
from archium.infrastructure.layout.geometry import Rect, grid_cells, split_horizontal


class HybridCanvasLayoutGenerator(LayoutGenerator):
    """Deterministic mixed layout — not freeform LLM coordinates."""

    family = LayoutFamily.HYBRID_CANVAS

    def generate(self, context: LayoutGeneratorContext) -> LayoutPlan:
        safe = self._safe(context.design_system)
        spacing = context.design_system.spacing
        elements: list[LayoutElement] = []

        title_h = 0.45
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
        left, right = split_horizontal(body, left_ratio=0.52, gap=spacing.lg)

        supports = list(context.content.supporting_asset_refs[:2])
        metrics = list(context.content.metrics[:3]) or [
            point for point in context.content.key_points if any(ch.isdigit() for ch in point)
        ][:3]
        captions = list(context.content.captions[:2])
        points = [
            point
            for point in context.content.key_points
            if point not in metrics
        ][:3]

        # Main drawing (prefer technical drawing treatment when a drawing hero is present).
        elements.append(
            LayoutElement(
                id="hero",
                role=LayoutElementRole.HERO_VISUAL,
                content_type=LayoutContentType.DRAWING,
                content_ref=context.content.hero_asset_ref,
                x=left.x,
                y=left.y,
                width=left.width,
                height=left.height * (0.88 if captions else 1.0),
                fit_mode=ImageFit.CONTAIN,
                crop_policy=CropPolicy.FORBIDDEN,
                style_token="drawing",
                locked=True,
            )
        )

        if captions:
            elements.append(
                LayoutElement(
                    id="hero_caption",
                    role=LayoutElementRole.CAPTION,
                    content_type=LayoutContentType.TEXT,
                    text_content=captions[0],
                    x=left.x,
                    y=left.y + left.height * 0.88 + spacing.xs,
                    width=left.width,
                    height=max(0.22, left.bottom - (left.y + left.height * 0.88 + spacing.xs)),
                    style_token="caption",
                )
            )

        # Right column: supports → metrics → text
        cursor_top = right.y
        support_ids: list[str] = []
        if supports:
            support_h = min(1.35, right.height * 0.38)
            support_area = Rect(right.x, cursor_top, right.width, support_h)
            cells = grid_cells(
                support_area,
                rows=1,
                cols=len(supports),
                gap_x=spacing.sm,
                gap_y=0,
            )
            for index, (cell, ref) in enumerate(zip(cells, supports, strict=True)):
                sid = f"support_{index}"
                support_ids.append(sid)
                elements.append(
                    LayoutElement(
                        id=sid,
                        role=LayoutElementRole.SUPPORTING_VISUAL,
                        content_type=LayoutContentType.IMAGE,
                        content_ref=ref,
                        x=cell.x,
                        y=cell.y,
                        width=cell.width,
                        height=cell.height,
                        fit_mode=ImageFit.COVER,
                        crop_policy=CropPolicy.SAFE_TRIM,
                        style_token="body",
                    )
                )
            cursor_top = support_area.bottom + spacing.sm

        metric_ids: list[str] = []
        if metrics:
            metric_h = min(0.7, right.bottom - cursor_top - 0.8)
            if metric_h >= 0.35:
                metric_area = Rect(right.x, cursor_top, right.width, metric_h)
                cells = grid_cells(
                    metric_area,
                    rows=1,
                    cols=len(metrics),
                    gap_x=spacing.xs,
                    gap_y=0,
                )
                for index, (cell, metric) in enumerate(zip(cells, metrics, strict=True)):
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
                cursor_top = metric_area.bottom + spacing.sm

        lead_h = min(0.55, max(0.28, right.bottom - cursor_top) * 0.35)
        elements.append(
            LayoutElement(
                id="lead",
                role=LayoutElementRole.LEAD_STATEMENT,
                content_type=LayoutContentType.TEXT,
                text_content=context.content.message,
                x=right.x,
                y=cursor_top,
                width=right.width,
                height=lead_h,
                style_token="subtitle",
            )
        )
        cursor_top = cursor_top + lead_h + spacing.xs

        if points and cursor_top < right.bottom - 0.25:
            points_text = "\n".join(f"· {point}" for point in points)
            body_bottom = right.bottom - (0.24 if len(captions) > 1 else 0.0)
            elements.append(
                LayoutElement(
                    id="body",
                    role=LayoutElementRole.BODY_TEXT,
                    content_type=LayoutContentType.TEXT,
                    text_content=points_text,
                    x=right.x,
                    y=cursor_top,
                    width=right.width,
                    height=max(0.35, body_bottom - cursor_top),
                    style_token="body",
                )
            )
            cursor_top = body_bottom

        if len(captions) > 1:
            elements.append(
                LayoutElement(
                    id="support_caption",
                    role=LayoutElementRole.CAPTION,
                    content_type=LayoutContentType.TEXT,
                    text_content=captions[1],
                    x=right.x,
                    y=right.bottom - 0.22,
                    width=right.width,
                    height=0.22,
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
                constraint_type=LayoutConstraintType.NO_OVERLAP,
                element_ids=[el.id for el in elements],
                priority=ConstraintPriority.REQUIRED,
            ),
            LayoutConstraint(
                constraint_type=LayoutConstraintType.PRESERVE_ASPECT_RATIO,
                element_ids=["hero"],
                priority=ConstraintPriority.REQUIRED,
            ),
        ]
        reading = ["title", "hero"]
        if any(el.id == "hero_caption" for el in elements):
            reading.append("hero_caption")
        reading.extend(support_ids)
        reading.extend(metric_ids)
        reading.append("lead")
        if any(el.id == "body" for el in elements):
            reading.append("body")
        if any(el.id == "support_caption" for el in elements):
            reading.append("support_caption")
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
