"""Unit of Work — Application API entry over a transactional SQLAlchemy Session.

Preferred UI / future HTTP entry:

    with application_api() as api:
        api.project.get(...)

    with unit_of_work() as uow:
        uow.api.jobs.create(...)
        LegacyService(uow).run(...)

    app = Application()
    with app.api() as api:
        api.jobs.list_active(project_id)

Nested / tests that already hold a Session:

    api = api_bound(session)  # or UnitOfWork.bind(session).api

Transaction ownership still follows APP-003: the outer ``get_session()``
(used inside :func:`unit_of_work`) commits on success / rolls back on error.
Application API methods flush only; :meth:`UnitOfWork.flush` is the explicit
mid-transaction sync point.

UI must prefer resource APIs (``api.project``, …) or ``with unit_of_work() as uow``
and pass ``uow`` as ``SessionLike``; unwrapping ``api.session`` / ``api.uow`` /
``uow.session`` in ``archium/ui`` is forbidden by layering tests (attributes remain
on Application types for internals/tests).
"""

from __future__ import annotations

from collections.abc import Generator, Iterator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from functools import cached_property
from typing import TYPE_CHECKING, Protocol, overload

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from archium.infrastructure.database import session as db_session

if TYPE_CHECKING:
    from archium.application.api.session import ApiContext


class UnitOfWorkFactory(Protocol):
    """Callable that opens one transactional UnitOfWork."""

    def __call__(
        self,
        engine: Engine | None = None,
        *,
        scoped: bool | None = None,
    ) -> AbstractContextManager[UnitOfWork]:
        ...


@dataclass
class UnitOfWork:
    """One transactional unit with a stable Application API facade.

    Prefer ``uow.api.*`` from UI. ``session`` remains an escape hatch for
    application services and tests that still need direct Session access
    (repositories, LangGraph, legacy helpers).
    """

    _session: Session

    @classmethod
    def bind(cls, session: Session) -> UnitOfWork:
        """Attach to an existing Session (tests / nested use-cases). Does not commit."""
        return cls(_session=session)

    @cached_property
    def api(self) -> ApiContext:
        from archium.application.api.session import ApiContext

        return ApiContext.from_uow(self)

    @property
    def session(self) -> Session:
        """Escape hatch — prefer ``api`` for product reads/writes."""
        return self._session

    def flush(self) -> None:
        """Flush pending ORM state without committing the transaction."""
        self._session.flush()


# Call-site union (Session | UnitOfWork): UI/facades may pass ``uow`` without
# unwrapping ``.session``. Not a persistence port — services still use
# :func:`session_of` → SQLAlchemy Session → concrete repositories.
# See ``docs/architecture/current-system.md`` §APP-029.
SessionLike = Session | UnitOfWork


@contextmanager
def unit_of_work(
    engine: Engine | None = None,
    *,
    scoped: bool | None = None,
) -> Generator[UnitOfWork, None, None]:
    """Open a transactional UoW (commit/rollback via ``get_session``)."""
    with db_session.get_session(engine, scoped=scoped) as session:
        yield UnitOfWork.bind(session)


@contextmanager
def application_api(
    engine: Engine | None = None,
    *,
    scoped: bool | None = None,
) -> Iterator[ApiContext]:
    """Preferred UI entry: yield :class:`ApiContext` (resource APIs), not a bare Session."""
    with unit_of_work(engine, scoped=scoped) as uow:
        yield uow.api


class Application:
    """Gateway yielding :class:`ApiContext` (resource APIs) for adapters.

    Use for future FastAPI / desktop adapters::

        app = Application()
        with app.api() as api:
            api.project.list()

    Streamlit may keep using :func:`application_api` directly; both share the
    same :class:`UnitOfWorkFactory`. ``ApiContext.session`` remains an Application
    escape hatch; UI must not unwrap it (layering tests).
    """

    def __init__(self, uow_factory: UnitOfWorkFactory | None = None) -> None:
        self._uow_factory: UnitOfWorkFactory = uow_factory or unit_of_work

    @contextmanager
    def api(
        self,
        engine: Engine | None = None,
        *,
        scoped: bool | None = None,
    ) -> Iterator[ApiContext]:
        with self._uow_factory(engine, scoped=scoped) as uow:
            yield uow.api

    @contextmanager
    def uow(
        self,
        engine: Engine | None = None,
        *,
        scoped: bool | None = None,
    ) -> Iterator[UnitOfWork]:
        with self._uow_factory(engine, scoped=scoped) as uow:
            yield uow


def get_application(uow_factory: UnitOfWorkFactory | None = None) -> Application:
    """Construct an Application gateway (tests may inject a fake factory)."""
    return Application(uow_factory=uow_factory)


def api_bound(session_or_uow: SessionLike) -> ApiContext:
    """Resolve Application API from a Session or an existing UnitOfWork.

    UI facades that still accept ``Session`` should call this once per
    function instead of repeating ``UnitOfWork.bind(session).api``.
    """
    if isinstance(session_or_uow, UnitOfWork):
        return session_or_uow.api
    return UnitOfWork.bind(session_or_uow).api


@overload
def session_of(session_or_uow: None) -> None: ...


@overload
def session_of(session_or_uow: SessionLike) -> Session: ...


def session_of(session_or_uow: SessionLike | None) -> Session | None:
    """Unwrap ``SessionLike`` to the underlying SQLAlchemy ``Session``.

    Application services use this at the boundary, then talk to concrete
    repositories. Compatibility only — not a repository/UoW port abstraction.
    """
    if session_or_uow is None:
        return None
    if isinstance(session_or_uow, UnitOfWork):
        return session_or_uow.session
    return session_or_uow
