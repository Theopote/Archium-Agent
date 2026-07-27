"""Unit tests for genesis starter draft seeding."""

from __future__ import annotations

from archium.application.genesis_starter_service import (
    ensure_genesis_starter_draft,
    get_genesis_starter_state,
)
from archium.application.product_continue_work import page_for_starter_draft
from archium.domain.project import Project
from archium.infrastructure.database.repositories import (
    PresentationRepository,
    ProjectRepository,
)


def test_ensure_genesis_starter_creates_outline_and_cover_slide(db_session) -> None:
    project = ProjectRepository(db_session).create(Project(name="青年文化中心"))
    db_session.commit()

    first = ensure_genesis_starter_draft(
        db_session,
        project.id,
        prompt="我想在西安做一个青年文化中心，强调公共性与地域性",
        project_name=project.name,
        understanding_summary="面向城市的青年文化聚合空间",
    )
    assert first.created is True
    assert first.has_first_slide is True
    assert first.page_count >= 6

    slides = PresentationRepository(db_session).list_slides(first.presentation_id)
    assert len(slides) == 1
    assert slides[0].order == 0

    second = ensure_genesis_starter_draft(
        db_session,
        project.id,
        prompt="重复调用",
        project_name=project.name,
    )
    assert second.created is False
    assert second.presentation_id == first.presentation_id


def test_get_genesis_starter_state_after_seed(db_session) -> None:
    project = ProjectRepository(db_session).create(Project(name="医院改造"))
    db_session.commit()
    ensure_genesis_starter_draft(
        db_session,
        project.id,
        prompt="医院改扩建汇报",
        project_name=project.name,
    )
    state = get_genesis_starter_state(db_session, project.id)
    assert state is not None
    assert state.page_count >= 6


def test_page_for_starter_draft_prefers_studio_before_layout(db_session) -> None:
    project = ProjectRepository(db_session).create(Project(name="草稿路由"))
    db_session.commit()
    starter = ensure_genesis_starter_draft(
        db_session,
        project.id,
        prompt="测试项目",
        project_name=project.name,
    )
    page = page_for_starter_draft(
        db_session,
        project.id,
        slide_count=1,
        layout_ready_count=0,
    )
    assert page == "edit"
    assert starter.has_first_slide
