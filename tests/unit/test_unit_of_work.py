"""Unit of Work + Application gateway boundary."""

from __future__ import annotations

from contextlib import contextmanager

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from archium.application.api.session import ApiContext, api_from_session
from archium.application.unit_of_work import (
    Application,
    UnitOfWork,
    api_bound,
    application_api,
    get_application,
    unit_of_work,
)
from archium.infrastructure.database.base import Base
from archium.infrastructure.database.repositories import ProjectRepository


@pytest.fixture()
def db_session(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    import archium.infrastructure.database.models  # noqa: F401

    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    @contextmanager
    def _get_session(*_args, **_kwargs):
        session = factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    import archium.infrastructure.database.session as session_mod

    monkeypatch.setattr(session_mod, "get_session", _get_session)

    session = factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def test_unit_of_work_bind_shares_api_cache(db_session: Session) -> None:
    uow = UnitOfWork.bind(db_session)
    assert uow.api is uow.api
    assert uow.session is db_session
    assert api_from_session(db_session) is not uow.api  # new bind → new ApiContext


def test_api_context_holds_unit_of_work(db_session: Session) -> None:
    uow = UnitOfWork.bind(db_session)
    api = uow.api
    assert isinstance(api, ApiContext)
    assert api.uow is uow
    assert api.session is db_session
    api.project.create("持有UoW", "")
    api.flush()
    listed = {p.name for p in api.project.list()}
    assert "持有UoW" in listed


def test_api_bound_accepts_session_or_uow(db_session: Session) -> None:
    uow = UnitOfWork.bind(db_session)
    assert api_bound(uow) is uow.api
    from_session = api_bound(db_session)
    assert from_session.session is db_session
    assert from_session.uow.session is db_session


def test_session_of_and_session_like(db_session: Session) -> None:
    from archium.application.unit_of_work import SessionLike, session_of

    uow = UnitOfWork.bind(db_session)
    assert session_of(db_session) is db_session
    assert session_of(uow) is db_session
    bound: SessionLike = uow
    assert api_bound(bound) is uow.api


def test_api_from_session_delegates_to_uow(db_session: Session) -> None:
    api = api_from_session(db_session)
    project = api.project.create("UoW项目", "d")
    assert ProjectRepository(db_session).get_by_id(project.id) is not None


def test_application_api_hides_session(db_session: Session) -> None:
    with application_api() as api:
        created = api.project.create("网关项目", "")
        assert created.name == "网关项目"
        assert isinstance(api.uow, UnitOfWork)


def test_application_gateway_injectable_factory(db_session: Session) -> None:
    @contextmanager
    def _factory(*_a, **_k):
        yield UnitOfWork.bind(db_session)

    app = get_application(uow_factory=_factory)
    with app.api() as api:
        listed = api.project.list()
        assert isinstance(listed, list)
    with app.uow() as uow:
        uow.flush()
        assert uow.api.project.list() is not None


def test_unit_of_work_context_commits_via_get_session(db_session: Session) -> None:
    with unit_of_work() as uow:
        project = uow.api.project.create("事务项目", "")
        project_id = project.id
    app = Application()
    with app.api() as api:
        names = [item.name for item in api.project.list()]
        assert "事务项目" in names
        assert any(item.id == project_id for item in api.project.list())
