"""Textual-argument layout generator."""

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
from archium.infrastructure.layout.geometry import Rect, split_horizontal


class TextualArgumentLayoutGenerator(LayoutGenerator):
    family = LayoutFamily.TEXTUAL_ARGUMENT

    def generate(self, context: LayoutGeneratorContext) -> LayoutPlan:
        safe = self._safe(context.design_system)
        spacing = context.design_system.spacing
        elements: list[LayoutElement] = []
        is_monument = context.variant == "monument"
        sparse_text_opener = is_monument or (
            context.variant in {"lead_and_points", None, ""}
            and not context.content.key_points
        )

        title_h = self._title_band_height(context)
        if sparse_text_opener:
            # Cover / sparse section: the title is the primary visual mass.
            title_h = max(title_h * 1.85, 1.15)
        elements.append(
            LayoutElement(
                id="title",
                role=LayoutElementRole.TITLE,
                content_type=LayoutContentType.TEXT,
                text_content=context.content.title,
                x=safe.x + (0.28 if sparse_text_opener else 0.0),
                y=safe.y,
                width=safe.width - (0.28 if sparse_text_opener else 0.0),
                height=title_h,
                style_token="title",
                z_index=2,
            )
        )

        body_top = safe.y + title_h + spacing.md
        body = Rect(safe.x, body_top, safe.width, max(1.0, safe.bottom - body_top - spacing.sm))

        if context.variant == "quote_argument":
            lead_w = body.width * 0.62
            lead_h = self._text_band_height(
                context,
                context.content.message,
                "title",
                box_width_in=lead_w,
                min_height=body.height * 0.35,
            )
            lead_h = min(lead_h, body.height * 0.85)
            elements.append(
                LayoutElement(
                    id="lead",
                    role=LayoutElementRole.LEAD_STATEMENT,
                    content_type=LayoutContentType.TEXT,
                    text_content=context.content.message,
                    x=body.x,
                    y=body.y + body.height * 0.08,
                    width=lead_w,
                    height=lead_h,
                    style_token="title",
                )
            )
            points = "\n".join(
                f"{index + 1:02}. {point}"
                for index, point in enumerate(context.content.key_points[:3])
            ) or "下一步行动待确认"
            elements.append(
                LayoutElement(
                    id="body",
                    role=LayoutElementRole.ANNOTATION,
                    content_type=LayoutContentType.TEXT,
                    text_content=points,
                    x=body.x + body.width * 0.72,
                    y=body.y + body.height * 0.56,
                    width=body.width * 0.28,
                    height=body.height * 0.28,
                    style_token="caption",
                )
            )
        elif is_monument:
            # Text-only memorial cover when no presentation-ready hero asset exists.
            # Keep hierarchy title > message; never leak system "missing asset" copy.
            colors = context.design_system.colors
            elements.append(
                LayoutElement(
                    id="accent_bar",
                    role=LayoutElementRole.DECORATION,
                    content_type=LayoutContentType.SHAPE,
                    x=safe.x,
                    y=safe.y,
                    width=0.12,
                    height=safe.height,
                    fill_color=colors.accent,
                    stroke_color=colors.accent,
                    stroke_width=0,
                    z_index=0,
                )
            )
            elements.append(
                LayoutElement(
                    id="title_rule",
                    role=LayoutElementRole.DECORATION,
                    content_type=LayoutContentType.SHAPE,
                    x=safe.x + 0.28,
                    y=safe.y + title_h + spacing.xs,
                    width=min(2.4, safe.width * 0.28),
                    height=0.04,
                    fill_color=colors.accent,
                    stroke_color=colors.accent,
                    stroke_width=0,
                    z_index=1,
                )
            )
            lead_h = min(
                body.height * 0.28,
                self._text_band_height(
                    context,
                    context.content.message or "",
                    "subtitle",
                    box_width_in=body.width * 0.78,
                    min_height=0.42,
                ),
            )
            if (context.content.message or "").strip():
                elements.append(
                    LayoutElement(
                        id="lead",
                        # Caption role keeps typography subordinate to the title band.
                        role=LayoutElementRole.CAPTION,
                        content_type=LayoutContentType.TEXT,
                        text_content=context.content.message,
                        x=body.x + 0.28,
                        y=body.y + spacing.sm,
                        width=body.width * 0.78,
                        height=lead_h,
                        style_token="caption",
                        z_index=2,
                    )
                )
            # Only render a body line for real key points — never invent system notices.
            if context.content.key_points:
                elements.append(
                    LayoutElement(
                        id="body",
                        role=LayoutElementRole.BODY_TEXT,
                        content_type=LayoutContentType.TEXT,
                        text_content=context.content.key_points[0],
                        x=body.x + 0.28,
                        y=body.y + spacing.sm + lead_h + spacing.md,
                        width=body.width * 0.62,
                        height=0.45,
                        style_token="caption",
                        z_index=2,
                    )
                )
        elif context.variant == "two_column_text":
            left, right = split_horizontal(body, left_ratio=0.48, gap=spacing.lg)
            elements.append(
                LayoutElement(
                    id="lead",
                    role=LayoutElementRole.LEAD_STATEMENT,
                    content_type=LayoutContentType.TEXT,
                    text_content=context.content.message,
                    x=left.x,
                    y=left.y,
                    width=left.width,
                    height=left.height,
                    style_token="body",
                )
            )
            points = "\n".join(f"· {point}" for point in context.content.key_points) or "· 要点待补充"
            elements.append(
                LayoutElement(
                    id="body",
                    role=LayoutElementRole.BODY_TEXT,
                    content_type=LayoutContentType.TEXT,
                    text_content=points,
                    x=right.x,
                    y=right.y,
                    width=right.width,
                    height=right.height,
                    style_token="body",
                )
            )
        else:
            # lead_and_points (default): message dominates; points only when real.
            has_points = bool(context.content.key_points)
            colors = context.design_system.colors
            if not has_points:
                # Sparse section opener — same editorial cues as monument, without
                # pretending this is a project cover.
                elements.append(
                    LayoutElement(
                        id="accent_bar",
                        role=LayoutElementRole.DECORATION,
                        content_type=LayoutContentType.SHAPE,
                        x=safe.x,
                        y=safe.y,
                        width=0.1,
                        height=safe.height * 0.55,
                        fill_color=colors.accent,
                        stroke_color=colors.accent,
                        stroke_width=0,
                        z_index=0,
                    )
                )
                elements.append(
                    LayoutElement(
                        id="title_rule",
                        role=LayoutElementRole.DECORATION,
                        content_type=LayoutContentType.SHAPE,
                        x=safe.x + 0.28,
                        y=safe.y + title_h + spacing.xs,
                        width=min(2.0, safe.width * 0.24),
                        height=0.035,
                        fill_color=colors.accent,
                        stroke_color=colors.accent,
                        stroke_width=0,
                        z_index=1,
                    )
                )
            lead_h = body.height * (0.42 if not has_points else 0.35)
            lead_h = min(
                lead_h,
                self._text_band_height(
                    context,
                    context.content.message,
                    "subtitle",
                    box_width_in=body.width * (0.82 if not has_points else 1.0),
                    min_height=0.5 if not has_points else body.height * 0.28,
                ),
            )
            elements.append(
                LayoutElement(
                    id="lead",
                    role=(
                        LayoutElementRole.CAPTION
                        if not has_points
                        else LayoutElementRole.LEAD_STATEMENT
                    ),
                    content_type=LayoutContentType.TEXT,
                    text_content=context.content.message,
                    x=body.x + (0.28 if not has_points else 0.0),
                    y=body.y + (spacing.sm if not has_points else 0.0),
                    width=body.width * (0.82 if not has_points else 1.0),
                    height=lead_h,
                    style_token="caption" if not has_points else "subtitle",
                    z_index=2,
                )
            )
            if has_points:
                points = "\n".join(f"· {point}" for point in context.content.key_points)
                elements.append(
                    LayoutElement(
                        id="body",
                        role=LayoutElementRole.BODY_TEXT,
                        content_type=LayoutContentType.TEXT,
                        text_content=points,
                        x=body.x,
                        y=body.y + lead_h + spacing.md,
                        width=body.width * (0.7 if context.content.hero_asset_ref else 1.0),
                        height=max(0.8, body.height - lead_h - spacing.md),
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
                    x=safe.x + (0.28 if is_monument else 0.0),
                    y=page.height - page.margin_bottom - 0.22,
                    width=safe.width * 0.7,
                    height=0.22,
                    style_token="source",
                )
            )

        content_ids = [
            el.id
            for el in elements
            if el.role != LayoutElementRole.DECORATION
        ]
        constraints = [
            LayoutConstraint(
                constraint_type=LayoutConstraintType.CONTAIN_WITHIN_SAFE_AREA,
                element_ids=[el.id for el in elements],
                priority=ConstraintPriority.REQUIRED,
            ),
            LayoutConstraint(
                constraint_type=LayoutConstraintType.NO_OVERLAP,
                element_ids=content_ids,
                priority=ConstraintPriority.REQUIRED,
            ),
        ]
        if any(el.id == "body" for el in elements):
            constraints.append(
                LayoutConstraint(
                    constraint_type=LayoutConstraintType.MIN_FONT_SIZE,
                    element_ids=["body"],
                    value=context.design_system.thresholds.min_body_font_pt,
                    priority=ConstraintPriority.REQUIRED,
                )
            )
        reading = [el.id for el in elements if el.role != LayoutElementRole.DECORATION]

        return self._build_plan(
            context,
            elements=elements,
            constraints=constraints,
            # Monument is a text cover — do not pretend the title is a hero visual.
            hero_element_id=None,
            reading_order=reading,
            balance_strategy="text_led",
        )
