"""Deck / slide delivery readiness — single page failure ≠ whole deck failure."""

from __future__ import annotations

from pydantic import Field

from archium.domain._base import DomainModel
from archium.domain.enums import DeckDeliveryStatus, SlideDeliveryStatus
from archium.domain.presentation import Presentation
from archium.domain.slide import SlideSpec

# Pages that can still appear in preview / Studio / draft export.
_DELIVERABLE_SLIDE_STATUSES = frozenset(
    {
        SlideDeliveryStatus.READY,
        SlideDeliveryStatus.FALLBACK_USED,
        SlideDeliveryStatus.ASSET_MISSING,
    }
)

_FAILED_SLIDE_STATUSES = frozenset(
    {
        SlideDeliveryStatus.FALLBACK_USED,
        SlideDeliveryStatus.ASSET_MISSING,
        SlideDeliveryStatus.RENDER_FAILED,
        SlideDeliveryStatus.SCHEMA_BLOCKED,
    }
)

_BLOCKING_SLIDE_STATUSES = frozenset(
    {
        SlideDeliveryStatus.RENDER_FAILED,
        SlideDeliveryStatus.SCHEMA_BLOCKED,
    }
)

_SKIPPED_SLIDE_STATUSES = frozenset({SlideDeliveryStatus.SKIPPED})


class DeckDeliveryReport(DomainModel):
    """Aggregated delivery view for a presentation deck."""

    status: DeckDeliveryStatus = DeckDeliveryStatus.READY
    total_slides: int = Field(default=0, ge=0)
    ready_count: int = Field(default=0, ge=0)
    failed_count: int = Field(default=0, ge=0)
    deliverable_count: int = Field(default=0, ge=0)
    failed_slide_orders: list[int] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @property
    def allows_preview(self) -> bool:
        return self.status in {
            DeckDeliveryStatus.READY,
            DeckDeliveryStatus.READY_WITH_FAILED_SLIDES,
            DeckDeliveryStatus.NEEDS_REVIEW,
        }

    @property
    def allows_draft_export(self) -> bool:
        return self.allows_preview and self.deliverable_count > 0


def is_slide_deliverable(status: SlideDeliveryStatus) -> bool:
    """Whether a page can still be previewed / exported as draft."""
    return status in _DELIVERABLE_SLIDE_STATUSES


def aggregate_deck_delivery(
    slides: list[SlideSpec],
    *,
    needs_review: bool = False,
) -> DeckDeliveryReport:
    """Derive deck delivery status from per-slide delivery statuses."""
    if not slides:
        return DeckDeliveryReport(
            status=DeckDeliveryStatus.BLOCKED,
            notes=["no slides available"],
        )

    ready = 0
    failed = 0
    deliverable = 0
    failed_orders: list[int] = []
    blocking = 0
    for slide in slides:
        status = slide.delivery_status
        if status in _SKIPPED_SLIDE_STATUSES:
            continue
        if status == SlideDeliveryStatus.READY:
            ready += 1
            deliverable += 1
            continue
        if status in _FAILED_SLIDE_STATUSES:
            failed += 1
            failed_orders.append(slide.order)
        if status in _DELIVERABLE_SLIDE_STATUSES:
            deliverable += 1
        if status in _BLOCKING_SLIDE_STATUSES:
            blocking += 1

    notes: list[str] = []
    if failed_orders:
        notes.append(
            "failed slides at orders: "
            + ", ".join(str(order) for order in sorted(failed_orders))
        )

    if ready == 0 and deliverable == 0:
        status = DeckDeliveryStatus.BLOCKED
    elif needs_review:
        status = DeckDeliveryStatus.NEEDS_REVIEW
    elif failed > 0 and deliverable > 0:
        status = DeckDeliveryStatus.READY_WITH_FAILED_SLIDES
    elif blocking > 0 and deliverable == 0:
        status = DeckDeliveryStatus.BLOCKED
    else:
        status = DeckDeliveryStatus.READY

    return DeckDeliveryReport(
        status=status,
        total_slides=len(slides),
        ready_count=ready,
        failed_count=failed,
        deliverable_count=deliverable,
        failed_slide_orders=sorted(failed_orders),
        notes=notes,
    )


def mark_slide_delivery(
    slide: SlideSpec,
    status: SlideDeliveryStatus,
    *,
    detail: str | None = None,
) -> SlideSpec:
    """Mutate and return slide with delivery status (for retry / soft-fail paths)."""
    slide.delivery_status = status
    slide.delivery_detail = (detail or "").strip() or None
    return slide


def refresh_slide_asset_delivery(slide: SlideSpec) -> SlideSpec:
    """Mark ASSET_MISSING when required visuals lack bound assets; clear when resolved.

    Does not upgrade FALLBACK_USED / RENDER_FAILED / SCHEMA_BLOCKED to READY.
    """
    from archium.domain.enums import VisualType

    required = [
        req
        for req in slide.visual_requirements
        if req.required and req.type != VisualType.TEXT_ONLY
    ]
    if not required:
        return slide

    def _is_bound(req: object) -> bool:
        if getattr(req, "type", None) == VisualType.ICON:
            return bool(getattr(req, "icon_id", None))
        return bool(getattr(req, "preferred_asset_ids", None))

    missing = [req for req in required if not _is_bound(req)]
    if missing:
        if slide.delivery_status in {
            SlideDeliveryStatus.READY,
            SlideDeliveryStatus.ASSET_MISSING,
        }:
            types = ", ".join(sorted({req.type.value for req in missing}))
            return mark_slide_delivery(
                slide,
                SlideDeliveryStatus.ASSET_MISSING,
                detail=f"missing required assets: {types}",
            )
        return slide

    if slide.delivery_status == SlideDeliveryStatus.ASSET_MISSING:
        return mark_slide_delivery(slide, SlideDeliveryStatus.READY)
    return slide


def apply_deck_delivery_to_presentation(
    presentation: Presentation,
    slides: list[SlideSpec],
    *,
    needs_review: bool = False,
) -> DeckDeliveryReport:
    """Aggregate slide delivery and write ``presentation.delivery_status``."""
    report = aggregate_deck_delivery(slides, needs_review=needs_review)
    presentation.delivery_status = report.status
    presentation.touch()
    return report
