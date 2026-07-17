"""Build PresentationSpec from domain presentation artifacts."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from archium.domain.enums import SlideType, VisualType
from archium.domain.presentation import PresentationBrief, Storyline
from archium.domain.presentation_spec import PresentationSpec, SpecImagePlacement, SpecSlide
from archium.domain.slide import SlideSpec

_LAYOUT_TITLE = "title"
_LAYOUT_THESIS = "thesis"
_LAYOUT_SECTION = "section"
_LAYOUT_CONTENT_BULLETS = "content_bullets"
_LAYOUT_CONTENT_MESSAGE = "content_message"
_LAYOUT_IMAGE_CONTENT = "image_content"
_LAYOUT_CLOSING = "closing"


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
    )


def _resolve_layout(slide: SlideSpec, *, has_images: bool) -> str:
    if has_images and slide.slide_type not in {SlideType.TITLE, SlideType.SECTION}:
        return _LAYOUT_IMAGE_CONTENT
    if slide.slide_type == SlideType.TITLE:
        return _LAYOUT_TITLE
    if slide.slide_type == SlideType.SECTION:
        return _LAYOUT_SECTION
    if slide.slide_type in {SlideType.CLOSING, SlideType.SUMMARY}:
        return _LAYOUT_CLOSING
    if slide.key_points:
        return _LAYOUT_CONTENT_BULLETS
    return _LAYOUT_CONTENT_MESSAGE


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
