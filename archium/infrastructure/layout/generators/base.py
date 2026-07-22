"""Base types for deterministic layout generators."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from uuid import UUID
from archium.domain.enums import VisualType

from archium.domain.slide import SlideSpec
from archium.domain.visual.art_direction import ArtDirection
from archium.domain.visual.design_system import DesignSystem
from archium.domain.visual.enums import LayoutFamily
from archium.domain.visual.layout import LayoutConstraint, LayoutElement, LayoutPlan
from archium.domain.visual.visual_intent import VisualIntent
from archium.infrastructure.layout.geometry import Rect, occupied_area, safe_area, whitespace_ratio


@dataclass
class LayoutContentBundle:
    """Content payload mapped onto generator regions."""

    title: str
    message: str = ""
    key_points: list[str] = field(default_factory=list)
    metrics: list[str] = field(default_factory=list)
    captions: list[str] = field(default_factory=list)
    source_text: str | None = None
    hero_asset_ref: str | None = None
    supporting_asset_refs: list[str] = field(default_factory=list)
    # Curated architectural icon refs (e.g. "icon:pedestrian_flow").
    # Used by specific layout generators to place semantic symbols.
    icon_refs: list[str] = field(default_factory=list)
    case_labels: list[str] = field(default_factory=list)
    comparison_dimensions: list[str] = field(default_factory=list)
    insight: str | None = None


@dataclass
class LayoutGeneratorContext:
    slide: SlideSpec
    visual_intent: VisualIntent
    art_direction: ArtDirection | None
    design_system: DesignSystem
    content: LayoutContentBundle
    variant: str


class LayoutGenerator(ABC):
    """Deterministic region generator for one LayoutFamily."""

    family: LayoutFamily

    @abstractmethod
    def generate(self, context: LayoutGeneratorContext) -> LayoutPlan:
        raise NotImplementedError

    def _safe(self, design_system: DesignSystem) -> Rect:
        return safe_area(design_system)

    def _build_plan(
        self,
        context: LayoutGeneratorContext,
        *,
        elements: list[LayoutElement],
        constraints: list[LayoutConstraint],
        hero_element_id: str | None,
        reading_order: list[str],
        balance_strategy: str,
        grid_rows: int | None = None,
    ) -> LayoutPlan:
        page = context.design_system.page
        occupied = occupied_area(
            [Rect(el.x, el.y, el.width, el.height) for el in elements]
        )
        return LayoutPlan(
            slide_id=context.slide.id,
            layout_family=self.family,
            layout_variant=context.variant,
            page_width=page.width,
            page_height=page.height,
            grid_columns=context.design_system.grid.columns,
            grid_rows=grid_rows,
            hero_element_id=hero_element_id,
            reading_order=reading_order,
            whitespace_ratio=whitespace_ratio(page, occupied),
            balance_strategy=balance_strategy,
            elements=elements,
            constraints=constraints,
            design_system_id=context.design_system.id,
            visual_intent_id=context.visual_intent.id,
        )

    def _text_band_height(
        self,
        context: LayoutGeneratorContext,
        text: str,
        style_token: str,
        *,
        box_width_in: float | None = None,
        min_height: float = 0.0,
    ) -> float:
        """Minimum element height so wrapped copy fits typography + repair slack."""
        from archium.infrastructure.layout.text_measurement import TextMeasurementService

        design_system = context.design_system
        safe = self._safe(design_system)
        width = box_width_in if box_width_in is not None else safe.width
        cleaned = text.strip()
        if not cleaned:
            return min_height
        typography = design_system.typography
        style = getattr(typography, style_token, typography.body)
        slack = design_system.thresholds.text_overflow_repair_slack_in
        needed = TextMeasurementService().estimate_block_height_in(
            cleaned,
            box_width_in=width,
            style=style,
            vertical_slack_in=slack,
        )
        return max(min_height, needed)

    def _title_band_height(
        self,
        context: LayoutGeneratorContext,
        title: str | None = None,
    ) -> float:
        return self._text_band_height(
            context,
            title or context.content.title or " ",
            "title",
            min_height=0.5,
        )


def asset_ref(asset_id: UUID | None, *, fallback: str | None = None) -> str | None:
    if asset_id is not None:
        return str(asset_id)
    return fallback


def content_from_slide(
    slide: SlideSpec,
    visual_intent: VisualIntent,
    *,
    source_text: str | None = None,
) -> LayoutContentBundle:
    """Build a content bundle from SlideSpec + VisualIntent asset refs."""
    hero = (
        str(visual_intent.hero_asset_id)
        if visual_intent.hero_asset_id is not None
        else None
    )
    supporting = [str(asset_id) for asset_id in visual_intent.supporting_asset_ids]
    if hero is None and slide.visual_requirements:
        primary = slide.visual_requirements[0].primary_asset_id
        if primary is not None:
            hero = str(primary)
    metrics = [point for point in slide.key_points if _looks_like_metric(point)]
    points = [point for point in slide.key_points if point not in metrics]
    citations = source_text
    if citations is None and slide.source_citations:
        first = slide.source_citations[0]
        citations = first.document_name
        if first.page_number is not None:
            citations = f"{citations} p.{first.page_number}"
    icon_refs = [
        f"icon:{req.icon_canonical_name}"
        for req in slide.visual_requirements
        if req.type == VisualType.ICON and req.icon_canonical_name
    ]
    return LayoutContentBundle(
        title=slide.title,
        message=slide.message,
        key_points=points,
        metrics=metrics,
        source_text=citations,
        hero_asset_ref=hero,
        supporting_asset_refs=supporting,
        icon_refs=icon_refs,
        case_labels=[point for point in points if "：" in point or ":" in point][:3],
        insight=slide.message if len(slide.message) < 120 else None,
    )


def _looks_like_metric(text: str) -> bool:
    stripped = text.strip()
    return any(ch.isdigit() for ch in stripped) and any(
        unit in stripped for unit in ("%", "㎡", "m²", "m2", "公顷", "人", "床", "层")
    )
