"""Unit tests for slide diff utilities."""

from __future__ import annotations

from uuid import uuid4

from archium.application.slide_diff import diff_snapshots, slide_to_snapshot
from archium.domain.enums import SlideStatus, SlideType
from archium.domain.slide import SlideSpec


def test_diff_snapshots_detects_field_changes() -> None:
    presentation_id = uuid4()
    before = slide_to_snapshot(
        SlideSpec(
            presentation_id=presentation_id,
            chapter_id="ch1",
            order=0,
            title="旧标题",
            message="旧观点。",
            slide_type=SlideType.CONTENT,
            key_points=["要点 A"],
            status=SlideStatus.PLANNED,
        )
    )
    after = slide_to_snapshot(
        SlideSpec(
            presentation_id=presentation_id,
            chapter_id="ch1",
            order=0,
            title="新标题",
            message="新观点。",
            slide_type=SlideType.CONTENT,
            key_points=["要点 B"],
            status=SlideStatus.DRAFT,
        )
    )

    result = diff_snapshots(
        before,
        after,
        slide_id=uuid4(),
        presentation_id=presentation_id,
        before_label="修订 #1",
        after_label="修订 #2",
    )

    assert result.has_changes
    changed_fields = {change.field for change in result.changes}
    assert {"title", "message", "key_points", "status"}.issubset(changed_fields)
    message_change = next(change for change in result.changes if change.field == "message")
    assert message_change.unified_diff is not None
