"""Build PresentationSpec from domain presentation artifacts."""

from __future__ import annotations

import re
from pathlib import Path
from uuid import UUID

from archium.domain.enums import SlideType, VisualType
from archium.domain.presentation import PresentationBrief, Storyline
from archium.domain.presentation_spec import (
    PresentationSpec,
    SpecColumn,
    SpecImagePlacement,
    SpecMetric,
    SpecSlide,
    SpecTimelineItem,
)
from archium.domain.slide import SlideSpec

_LAYOUT_TITLE = "title"
_LAYOUT_THESIS = "thesis"
_LAYOUT_SECTION = "section"
_LAYOUT_CONTENT_BULLETS = "content_bullets"
_LAYOUT_CONTENT_MESSAGE = "content_message"
_LAYOUT_IMAGE_CONTENT = "image_content"
_LAYOUT_IMAGE_FULL = "image_full"
_LAYOUT_COMPARISON = "comparison"
_LAYOUT_TIMELINE = "timeline"
_LAYOUT_DATA = "data"
_LAYOUT_CLOSING = "closing"

_LABEL_SPLIT_PATTERN = re.compile(r"^([^：:|]+)[：:|]\s*(.+)$")


def build_presentation_spec(
    *,
    presentation_id: UUID,
    brief: PresentationBrief,
    storyline: Storyline,
    slides: list[SlideSpec],
    version: int = 1,
    theme: str = "archium-default",
    asset_paths: dict[UUID, Path] | None = None,
) -> PresentationSpec:
    """Convert Brief / Storyline / SlideSpec into a renderer-agnostic spec."""
    resolved_assets = asset_paths or {}
    spec_slides: list[SpecSlide] = [
        SpecSlide(
            order=0,
            layout=_LAYOUT_TITLE,
            title=brief.title,
            subtitle=brief.audience,
            message=brief.core_message or None,
        )
    ]

    if storyline.thesis.strip():
        spec_slides.append(
            SpecSlide(
                order=len(spec_slides),
                layout=_LAYOUT_THESIS,
                title="总体论点",
                message=storyline.thesis.strip(),
            )
        )

    for slide in sorted(slides, key=lambda item: item.order):
        spec_slides.append(
            _build_spec_slide(
                slide,
                order=len(spec_slides),
                asset_paths=resolved_assets,
            )
        )

    return PresentationSpec(
        presentation_id=str(presentation_id),
        version=version,
        title=brief.title,
        theme=theme,
        language=brief.language,
        slides=spec_slides,
    )


def _build_spec_slide(
    slide: SlideSpec,
    *,
    order: int,
    asset_paths: dict[UUID, Path],
) -> SpecSlide:
    images = _build_image_placements(slide, asset_paths)
    layout = _resolve_layout(slide, has_images=bool(images))
    subtitle = None
    message = slide.message.strip() or None
    bullets = list(slide.key_points)

    if slide.slide_type == SlideType.SECTION and message:
        subtitle = message
        message = None
    if slide.slide_type == SlideType.TITLE:
        subtitle = message
        message = None

    columns: list[SpecColumn] = []
    timeline_items: list[SpecTimelineItem] = []
    metrics: list[SpecMetric] = []

    if layout == _LAYOUT_COMPARISON:
        columns = _build_comparison_columns(slide)
        bullets = []
    elif layout == _LAYOUT_TIMELINE:
        timeline_items = _build_timeline_items(slide.key_points)
        bullets = []
    elif layout == _LAYOUT_DATA:
        metrics = _build_metrics(slide.key_points)
        bullets = []
    elif layout == _LAYOUT_IMAGE_FULL and images:
        images = [_full_bleed_image(images[0])]

    notes = slide.speaker_notes.strip() if slide.speaker_notes else None
    if slide.source_citations:
        citation_lines = [
            f"{citation.document_name}"
            + (f" p.{citation.page_number}" if citation.page_number else "")
            for citation in slide.source_citations
        ]
        citation_block = "来源：\n" + "\n".join(f"- {line}" for line in citation_lines)
        notes = f"{notes}\n\n{citation_block}".strip() if notes else citation_block

    return SpecSlide(
        order=order,
        layout=layout,
        title=slide.title,
        subtitle=subtitle,
        message=message,
        bullets=bullets,
        speaker_notes=notes,
        images=images,
        columns=columns,
        timeline_items=timeline_items,
        metrics=metrics,
    )


def _resolve_layout(slide: SlideSpec, *, has_images: bool) -> str:
    if slide.slide_type == SlideType.TITLE:
        return _LAYOUT_TITLE
    if slide.slide_type == SlideType.SECTION:
        return _LAYOUT_SECTION
    if slide.slide_type in {SlideType.CLOSING, SlideType.SUMMARY}:
        return _LAYOUT_CLOSING
    if slide.slide_type == SlideType.COMPARISON:
        return _LAYOUT_COMPARISON
    if slide.slide_type == SlideType.TIMELINE:
        return _LAYOUT_TIMELINE
    if slide.slide_type == SlideType.DATA:
        return _LAYOUT_DATA
    if slide.slide_type == SlideType.IMAGE:
        return _LAYOUT_IMAGE_FULL if has_images else _LAYOUT_CONTENT_MESSAGE
    if has_images:
        return _LAYOUT_IMAGE_CONTENT
    if slide.key_points:
        return _LAYOUT_CONTENT_BULLETS
    return _LAYOUT_CONTENT_MESSAGE


def _build_comparison_columns(slide: SlideSpec) -> list[SpecColumn]:
    points = list(slide.key_points)
    if len(points) >= 2:
        mid = (len(points) + 1) // 2
        left_points = points[:mid]
        right_points = points[mid:]
    elif len(points) == 1:
        left_points = [points[0]]
        right_points = []
    else:
        left_points = []
        right_points = []

    left_label, right_label = "改造前", "改造后"
    left_bullets = left_points
    right_bullets = right_points

    parsed_left = _parse_labeled_point(left_points[0]) if len(left_points) == 1 else None
    parsed_right = _parse_labeled_point(right_points[0]) if len(right_points) == 1 else None
    if parsed_left and parsed_right and len(left_points) == 1 and len(right_points) == 1:
        left_label, left_bullets = parsed_left[0], [parsed_left[1]]
        right_label, right_bullets = parsed_right[0], [parsed_right[1]]

    return [
        SpecColumn(label=left_label, bullets=left_bullets),
        SpecColumn(label=right_label, bullets=right_bullets),
    ]


def _build_timeline_items(key_points: list[str]) -> list[SpecTimelineItem]:
    items: list[SpecTimelineItem] = []
    for index, point in enumerate(key_points, start=1):
        parsed = _parse_labeled_point(point)
        if parsed is not None:
            items.append(SpecTimelineItem(label=parsed[0], text=parsed[1]))
        else:
            items.append(SpecTimelineItem(label=f"阶段 {index}", text=point))
    return items


def _build_metrics(key_points: list[str]) -> list[SpecMetric]:
    metrics: list[SpecMetric] = []
    for point in key_points:
        parsed = _parse_labeled_point(point)
        if parsed is not None:
            metrics.append(SpecMetric(label=parsed[0], value=parsed[1]))
        else:
            metrics.append(SpecMetric(label=point, value="—"))
    return metrics


def _parse_labeled_point(text: str) -> tuple[str, str] | None:
    match = _LABEL_SPLIT_PATTERN.match(text.strip())
    if match is None:
        return None
    return match.group(1).strip(), match.group(2).strip()


def _full_bleed_image(placement: SpecImagePlacement) -> SpecImagePlacement:
    return SpecImagePlacement(
        description=placement.description,
        asset_path=placement.asset_path,
        x=0.7,
        y=1.45,
        w=8.6,
        h=3.85,
    )


def _build_image_placements(
    slide: SlideSpec,
    asset_paths: dict[UUID, Path],
) -> list[SpecImagePlacement]:
    placements: list[SpecImagePlacement] = []
    for index, requirement in enumerate(slide.visual_requirements):
        if requirement.type == VisualType.TEXT_ONLY:
            continue
        asset_id = requirement.primary_asset_id
        asset_path = None
        if asset_id is not None:
            resolved = asset_paths.get(asset_id)
            if resolved is not None and resolved.exists():
                asset_path = str(resolved)
        placements.append(
            SpecImagePlacement(
                description=requirement.description,
                asset_path=asset_path,
                x=5.0,
                y=1.5 + index * 0.2,
                w=4.0,
                h=3.5,
            )
        )
    return placements
