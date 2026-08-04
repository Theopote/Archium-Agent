"""Unit of Work + Application gateway boundary."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
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
from archium.domain.project import Project
from archium.infrastructure.database.base import Base
from archium.infrastructure.database.repositories import ProjectRepository


@pytest.fixture()
def memory_engine() -> Generator[Engine, None, None]:
    """Isolated in-memory engine — pass to unit_of_work / application_api / Application."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    import archium.infrastructure.database.models  # noqa: F401

    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture()
def db_session(memory_engine: Engine) -> Generator[Session, None, None]:
    session = Session(
        bind=memory_engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    try:
        yield session
    finally:
        session.close()


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
    from archium.application.project_knowledge_service import ProjectKnowledgeService
    from archium.application.unit_of_work import SessionLike, session_of

    uow = UnitOfWork.bind(db_session)
    assert session_of(db_session) is db_session
    assert session_of(uow) is db_session
    bound: SessionLike = uow
    assert api_bound(bound) is uow.api
    # Application services accept UnitOfWork directly
    service = ProjectKnowledgeService(uow)
    assert service._session is db_session


def test_api_from_session_delegates_to_uow(db_session: Session) -> None:
    api = api_from_session(db_session)
    project = api.project.create("UoW项目", "d")
    assert ProjectRepository(db_session).get_by_id(project.id) is not None


def test_application_api_hides_session(memory_engine: Engine) -> None:
    with application_api(memory_engine) as api:
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


def test_unit_of_work_context_commits_via_get_session(memory_engine: Engine) -> None:
    """``unit_of_work(engine)`` commits through real ``get_session`` — no monkeypatch."""
    with unit_of_work(memory_engine) as uow:
        project = uow.api.project.create("事务项目", "")
        project_id = project.id

    # Fresh Application gateway on the same engine must see committed rows.
    app = Application()
    with app.api(memory_engine) as api:
        names = [item.name for item in api.project.list()]
        assert "事务项目" in names
        assert any(item.id == project_id for item in api.project.list())

    # Independent Session (not via UoW) also sees the commit.
    verify = Session(bind=memory_engine, autoflush=False, autocommit=False)
    try:
        assert ProjectRepository(verify).get_by_id(project_id) is not None
    finally:
        verify.close()


def _insert_project(session: Session, name: str) -> Project:
    """Flush-only insert — avoid ProjectManagementService (APP-003 mid-txn commit)."""
    return ProjectRepository(session).create(Project(name=name, description=""))


def test_unit_of_work_rolls_back_on_exception(memory_engine: Engine) -> None:
    project_id = None
    with pytest.raises(RuntimeError, match="boom"):
        with unit_of_work(memory_engine) as uow:
            created = _insert_project(uow.session, "回滚项目")
            project_id = created.id
            uow.flush()
            raise RuntimeError("boom")

    assert project_id is not None
    verify = Session(bind=memory_engine, autoflush=False, autocommit=False)
    try:
        assert ProjectRepository(verify).get_by_id(project_id) is None
    finally:
        verify.close()


def test_flush_does_not_commit(memory_engine: Engine) -> None:
    """Flush + exception still rolls back — flush is not a commit boundary."""
    project_id = None
    with pytest.raises(ValueError, match="after-flush"):
        with unit_of_work(memory_engine) as uow:
            created = _insert_project(uow.session, "仅flush")
            project_id = created.id
            uow.flush()
            assert ProjectRepository(uow.session).get_by_id(project_id) is not None
            raise ValueError("after-flush")

    verify = Session(bind=memory_engine, autoflush=False, autocommit=False)
    try:
        assert ProjectRepository(verify).get_by_id(project_id) is None
    finally:
        verify.close()


def test_bound_uow_does_not_commit_owner_session(db_session: Session) -> None:
    uow = UnitOfWork.bind(db_session)
    created = _insert_project(uow.session, "绑定不提交")
    uow.flush()
    assert ProjectRepository(db_session).get_by_id(created.id) is not None

    db_session.rollback()
    assert ProjectRepository(db_session).get_by_id(created.id) is None


def test_nested_bound_uow_does_not_close_session(db_session: Session) -> None:
    outer = UnitOfWork.bind(db_session)
    inner = UnitOfWork.bind(db_session)
    assert outer.session is db_session
    assert inner.session is db_session
    created = _insert_project(inner.session, "嵌套绑定")
    outer.flush()
    assert ProjectRepository(outer.session).get_by_id(created.id) is not None
    assert db_session.is_active


def test_application_api_uses_fresh_session_per_entry(memory_engine: Engine) -> None:
    """Each ``application_api`` entry owns an independent Session (closed on exit)."""
    with application_api(memory_engine) as api:
        first = api.uow.session
        _insert_project(first, "跨次入口可见")
    with application_api(memory_engine) as api:
        second = api.uow.session
        assert first is not second
        names = {p.name for p in ProjectRepository(second).list_all()}
        assert "跨次入口可见" in names


def test_unit_of_work_scoped_false_commits_independent_session(memory_engine: Engine) -> None:
    """Worker-style ``scoped=False`` still commits on success via get_session."""
    with unit_of_work(memory_engine, scoped=False) as uow:
        first = uow.session
        _insert_project(first, "worker独立会话")
    with unit_of_work(memory_engine, scoped=False) as uow:
        assert uow.session is not first
        names = {p.name for p in ProjectRepository(uow.session).list_all()}
        assert "worker独立会话" in names


def test_commit_failure_rolls_back(memory_engine: Engine, monkeypatch: pytest.MonkeyPatch) -> None:
    """If outer commit fails, pending work must not remain visible."""
    from archium.infrastructure.database import session as db_session_mod

    project_id = None

    @contextmanager
    def _failing_commit(engine=None):
        factory = db_session_mod.get_session_factory(engine)
        session = factory()
        try:
            yield session
            raise RuntimeError("commit failed")
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    monkeypatch.setattr(db_session_mod, "_independent_session", _failing_commit)

    with pytest.raises(RuntimeError, match="commit failed"):
        with unit_of_work(memory_engine) as uow:
            created = _insert_project(uow.session, "提交失败")
            project_id = created.id
            uow.flush()

    verify = Session(bind=memory_engine, autoflush=False, autocommit=False)
    try:
        assert ProjectRepository(verify).get_by_id(project_id) is None
    finally:
        verify.close()
