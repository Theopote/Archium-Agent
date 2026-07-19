"""Unit tests for slide snapshot restore helpers."""

from __future__ import annotations

from uuid import uuid4

from archium.application.slide_diff import (
    slide_to_snapshot,
    snapshot_content_fingerprint,
    snapshot_to_slide,
)
from archium.domain.enums import SlideStatus, SlideType
from archium.domain.slide import SlideSpec


def test_snapshot_to_slide_restores_content_fields() -> None:
    slide = SlideSpec(
        presentation_id=uuid4(),
        chapter_id="ch1",
        order=0,
        title="旧标题",
        message="旧信息",
        slide_type=SlideType.CONTENT,
        key_points=["a"],
        status=SlideStatus.PLANNED,
        version=1,
    )
    snapshot = slide_to_snapshot(slide.model_copy(update={"title": "新标题", "message": "新信息", "key_points": ["a", "b"]}))
    restored = snapshot_to_slide(snapshot, slide)
    assert restored.title == "新标题"
    assert restored.message == "新信息"
    assert restored.key_points == ["a", "b"]
    assert restored.version == 2


def test_snapshot_content_fingerprint_ignores_version() -> None:
    first = {"title": "A", "message": "B", "key_points": ["x"], "speaker_notes": None, "slide_type": "content", "status": "planned", "version": 1}
    second = dict(first)
    second["version"] = 9
    assert snapshot_content_fingerprint(first) == snapshot_content_fingerprint(second)
