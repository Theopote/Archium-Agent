"""Prefer a presentation with slides when auto-selecting a project deck."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session
from archium.application.unit_of_work import SessionLike, session_of

from archium.domain.presentation import Presentation
from archium.infrastructure.database.repositories import PresentationRepository


def _as_uuid(value: UUID | str | None) -> UUID | None:
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


def select_presentation(
    session: SessionLike,
    presentations: list[Presentation],
    *,
    preferred_id: UUID | str | None = None,
    keep_empty_preferred: bool = False,
) -> Presentation | None:
    """Pick a presentation for Studio / Deliver / progress chrome.

    Auto-default prefers decks that already have slides (avoids locking onto a
    newly created empty shell when an older deck has content). Explicit empty
    preferred ids are kept only when ``keep_empty_preferred`` is True.
    """
    session = session_of(session)
    if not presentations:
        return None

    by_id = {item.id: item for item in presentations}
    preferred_uuid = _as_uuid(preferred_id)
    preferred = by_id.get(preferred_uuid) if preferred_uuid is not None else None
    repo = PresentationRepository(session)

    def has_slides(presentation: Presentation) -> bool:
        return bool(repo.list_slides(presentation.id))

    nonempty = [item for item in presentations if has_slides(item)]
    if preferred is not None and (
        keep_empty_preferred or has_slides(preferred) or not nonempty
    ):
        return preferred

    pool = nonempty or list(presentations)
    return max(pool, key=lambda item: item.updated_at)
