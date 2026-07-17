"""Unit tests for slide lineage helpers."""

from __future__ import annotations

from uuid import uuid4

from archium.application.slide_lineage import apply_slide_lineage
from archium.domain.enums import SlideType
from archium.domain.slide import SlideSpec, build_slide_logical_key


def test_apply_slide_lineage_reuses_matching_key() -> None:
    presentation_id = uuid4()
    previous = SlideSpec(
        presentation_id=presentation_id,
        chapter_id="ch-strategy",
        order=1,
        title="旧页",
        message="旧观点。",
        slide_type=SlideType.CONTENT,
        version=2,
    )
    new_slide = SlideSpec(
        presentation_id=presentation_id,
        chapter_id="ch-strategy",
        order=1,
        title="新页",
        message="新观点。",
        slide_type=SlideType.CONTENT,
    )

    apply_slide_lineage([new_slide], [previous])

    assert new_slide.lineage_id == previous.lineage_id
    assert new_slide.logical_key == build_slide_logical_key("ch-strategy", 1)
    assert new_slide.version == 3


def test_apply_slide_lineage_assigns_new_lineage_for_new_key() -> None:
    presentation_id = uuid4()
    previous = SlideSpec(
        presentation_id=presentation_id,
        chapter_id="ch1",
        order=0,
        title="旧页",
        message="旧观点。",
        slide_type=SlideType.CONTENT,
    )
    new_slide = SlideSpec(
        presentation_id=presentation_id,
        chapter_id="ch2",
        order=0,
        title="新增页",
        message="新观点。",
        slide_type=SlideType.CONTENT,
    )

    apply_slide_lineage([new_slide], [previous])

    assert new_slide.lineage_id != previous.lineage_id
    assert new_slide.version == 1
