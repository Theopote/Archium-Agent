"""Tests for presentation auto-selection preferring decks with slides."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from uuid import uuid4

from archium.application.presentation_selection import select_presentation
from archium.domain.enums import PresentationStatus
from archium.domain.presentation import Presentation


def _presentation(*, title: str, updated_at: datetime) -> Presentation:
    return Presentation(
        id=uuid4(),
        project_id=uuid4(),
        title=title,
        status=PresentationStatus.DRAFT,
        updated_at=updated_at,
        created_at=updated_at,
    )


def test_select_presentation_prefers_nonempty_over_newer_empty() -> None:
    older = _presentation(
        title="UI验收稿",
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    newer_empty = _presentation(
        title="概念汇报",
        updated_at=datetime(2026, 7, 1, tzinfo=UTC),
    )
    session = MagicMock()
    slides = {
        older.id: [object()],
        newer_empty.id: [],
    }

    class _Repo:
        def __init__(self, _session: object) -> None:
            pass

        def list_slides(self, presentation_id):
            return slides.get(presentation_id, [])

    import archium.application.presentation_selection as mod

    original = mod.PresentationRepository
    mod.PresentationRepository = _Repo  # type: ignore[misc, assignment]
    try:
        picked = select_presentation(session, [newer_empty, older])
        assert picked is not None
        assert picked.id == older.id
    finally:
        mod.PresentationRepository = original  # type: ignore[misc]


def test_select_presentation_keeps_empty_when_requested() -> None:
    empty = _presentation(
        title="空壳",
        updated_at=datetime.now(UTC),
    )
    filled = _presentation(
        title="有页",
        updated_at=datetime.now(UTC) - timedelta(days=1),
    )
    session = MagicMock()
    slides = {empty.id: [], filled.id: [object()]}

    class _Repo:
        def __init__(self, _session: object) -> None:
            pass

        def list_slides(self, presentation_id):
            return slides.get(presentation_id, [])

    import archium.application.presentation_selection as mod

    original = mod.PresentationRepository
    mod.PresentationRepository = _Repo  # type: ignore[misc, assignment]
    try:
        picked = select_presentation(
            session,
            [empty, filled],
            preferred_id=empty.id,
            keep_empty_preferred=True,
        )
        assert picked is not None
        assert picked.id == empty.id
    finally:
        mod.PresentationRepository = original  # type: ignore[misc]
