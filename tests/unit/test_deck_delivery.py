"""Unit tests for deck / slide delivery aggregation."""

from __future__ import annotations

from uuid import uuid4

from archium.domain.deck_delivery import (
    aggregate_deck_delivery,
    is_slide_deliverable,
    mark_slide_delivery,
)
from archium.domain.enums import DeckDeliveryStatus, SlideDeliveryStatus
from archium.domain.slide import SlideSpec


def _slide(
    order: int,
    status: SlideDeliveryStatus = SlideDeliveryStatus.READY,
) -> SlideSpec:
    slide = SlideSpec(
        presentation_id=uuid4(),
        chapter_id="ch1",
        order=order,
        title=f"页{order}",
        message="核心观点需要足够长度。",
    )
    return mark_slide_delivery(slide, status, detail=status.value)


def test_single_failed_page_keeps_deck_exportable() -> None:
    slides = [
        _slide(0, SlideDeliveryStatus.READY),
        _slide(1, SlideDeliveryStatus.FALLBACK_USED),
        _slide(2, SlideDeliveryStatus.READY),
    ]
    report = aggregate_deck_delivery(slides)
    assert report.status == DeckDeliveryStatus.READY_WITH_FAILED_SLIDES
    assert report.allows_preview is True
    assert report.allows_draft_export is True
    assert report.failed_slide_orders == [1]
    assert report.deliverable_count == 3


def test_all_blocking_pages_block_deck() -> None:
    slides = [
        _slide(0, SlideDeliveryStatus.RENDER_FAILED),
        _slide(1, SlideDeliveryStatus.SCHEMA_BLOCKED),
    ]
    report = aggregate_deck_delivery(slides)
    assert report.status == DeckDeliveryStatus.BLOCKED
    assert report.allows_preview is False
    assert report.allows_draft_export is False


def test_needs_review_overrides_ready() -> None:
    slides = [_slide(0), _slide(1)]
    report = aggregate_deck_delivery(slides, needs_review=True)
    assert report.status == DeckDeliveryStatus.NEEDS_REVIEW
    assert report.allows_preview is True


def test_asset_missing_still_deliverable() -> None:
    assert is_slide_deliverable(SlideDeliveryStatus.ASSET_MISSING) is True
    assert is_slide_deliverable(SlideDeliveryStatus.RENDER_FAILED) is False
    slides = [
        _slide(0, SlideDeliveryStatus.READY),
        _slide(1, SlideDeliveryStatus.ASSET_MISSING),
    ]
    report = aggregate_deck_delivery(slides)
    assert report.status == DeckDeliveryStatus.READY_WITH_FAILED_SLIDES
    assert report.allows_draft_export is True


def test_empty_deck_is_blocked() -> None:
    report = aggregate_deck_delivery([])
    assert report.status == DeckDeliveryStatus.BLOCKED


def test_refresh_slide_asset_delivery_marks_missing() -> None:
    from archium.domain.enums import VisualType
    from archium.domain.deck_delivery import refresh_slide_asset_delivery
    from archium.domain.slide import VisualRequirement

    slide = _slide(0, SlideDeliveryStatus.READY)
    slide.visual_requirements = [
        VisualRequirement(
            type=VisualType.SITE_PLAN,
            description="总平面图",
            required=True,
        )
    ]
    refresh_slide_asset_delivery(slide)
    assert slide.delivery_status == SlideDeliveryStatus.ASSET_MISSING
