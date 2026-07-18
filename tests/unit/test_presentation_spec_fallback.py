"""Unit tests for fallback image paths in PresentationSpec."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from archium.domain.enums import PresentationType, SlideType, VisualType
from archium.domain.fallback_image import FallbackImage
from archium.domain.presentation import Chapter, PresentationBrief, Storyline
from archium.domain.slide import SlideSpec, VisualRequirement
from archium.infrastructure.renderers.presentation_spec_builder import build_presentation_spec


def test_build_presentation_spec_uses_fallback_image_path(tmp_path: Path) -> None:
    presentation_id = uuid4()
    slide_id = uuid4()
    fallback_file = tmp_path / "generated.png"
    fallback_file.write_bytes(b"png")

    brief = PresentationBrief(
        project_id=uuid4(),
        presentation_id=presentation_id,
        title="Brief",
        presentation_type=PresentationType.CLIENT_REVIEW,
        audience="客户",
        purpose="汇报",
        duration_minutes=15,
        target_slide_count=8,
        core_message="核心",
    )
    storyline = Storyline(
        presentation_id=presentation_id,
        thesis="论点",
        chapters=[
            Chapter(
                id="ch1",
                title="章节",
                purpose="展开论述",
                key_message="核心观点",
                order=0,
            )
        ],
    )
    slide = SlideSpec(
        id=slide_id,
        presentation_id=presentation_id,
        chapter_id="ch1",
        order=0,
        title="流线示意",
        message="交通组织",
        slide_type=SlideType.CONTENT,
        visual_requirements=[
            VisualRequirement(
                type=VisualType.DIAGRAM,
                description="交通流线示意",
                required=True,
            )
        ],
    )

    spec = build_presentation_spec(
        presentation_id=presentation_id,
        brief=brief,
        storyline=storyline,
        slides=[slide],
        fallback_images={
            (slide_id, 0): FallbackImage(
                path=fallback_file,
                generated=True,
                web_sourced=True,
                attribution="Photo by Jane on Pexels",
                source_url="https://www.pexels.com/photo/1/",
            )
        },
    )

    content_slide = spec.slides[-1]
    assert content_slide.images[0].asset_path == str(fallback_file)
    assert content_slide.images[0].generated is True
    assert content_slide.images[0].web_sourced is True
    assert "Jane" in (content_slide.speaker_notes or "")
