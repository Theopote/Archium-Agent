"""Unit tests for genesis starter draft seeding."""

from __future__ import annotations

from pathlib import Path

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
    assert first.slides_ready_count >= 6
    assert first.layout_ready_count >= 6
    assert first.layout_ready_count == first.page_count

    slides = PresentationRepository(db_session).list_slides(first.presentation_id)
    assert len(slides) == first.page_count
    assert slides[0].order == 0
    assert all(slide.message.strip() for slide in slides)
    assert all(slide.layout_plan_id is not None for slide in slides)
    assert {slide.order for slide in slides} == set(range(first.page_count))

    second = ensure_genesis_starter_draft(
        db_session,
        project.id,
        prompt="重复调用",
        project_name=project.name,
    )
    assert second.created is False
    assert second.presentation_id == first.presentation_id
    assert second.layout_ready_count == first.page_count


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
    assert state.layout_ready_count == state.page_count


def test_ensure_genesis_starter_creates_cover_wireframe(db_session) -> None:
    project = ProjectRepository(db_session).create(Project(name="封面线框"))
    db_session.commit()

    result = ensure_genesis_starter_draft(
        db_session,
        project.id,
        prompt="城市更新汇报封面",
        project_name=project.name,
        understanding_summary="以公共性为主轴的更新策略",
    )
    slides = PresentationRepository(db_session).list_slides(result.presentation_id)
    assert slides
    assert slides[0].layout_plan_id is not None
    assert result.has_cover_layout or slides[0].layout_plan_id is not None
    assert result.cover_preview_path is None or Path(result.cover_preview_path).is_file()


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
        slide_count=starter.slides_ready_count,
        layout_ready_count=0,
    )
    assert page == "edit"
    assert starter.has_first_slide


def test_existing_starter_backfills_missing_placeholder_slides(db_session) -> None:
    project = ProjectRepository(db_session).create(Project(name="回填测试"))
    db_session.commit()
    first = ensure_genesis_starter_draft(
        db_session,
        project.id,
        prompt="测试回填",
        project_name=project.name,
    )
    repo = PresentationRepository(db_session)
    for slide in repo.list_slides(first.presentation_id):
        if slide.order > 0:
            repo.delete_slide(slide.id)
    db_session.commit()

    state = get_genesis_starter_state(db_session, project.id)
    assert state is not None
    assert state.slides_ready_count == state.page_count
    assert state.layout_ready_count == state.page_count
    assert state.page_count >= 6


def test_ensure_deck_wireframe_layouts_is_idempotent(db_session) -> None:
    from archium.application.genesis_cover_layout_service import ensure_deck_wireframe_layouts

    project = ProjectRepository(db_session).create(Project(name="线框幂等"))
    db_session.commit()
    starter = ensure_genesis_starter_draft(
        db_session,
        project.id,
        prompt="幂等测试",
        project_name=project.name,
    )
    first = ensure_deck_wireframe_layouts(
        db_session,
        project_id=project.id,
        presentation_id=starter.presentation_id,
    )
    second = ensure_deck_wireframe_layouts(
        db_session,
        project_id=project.id,
        presentation_id=starter.presentation_id,
    )
    assert first.layout_ready_count == starter.page_count
    assert second.applied_count == 0
    assert second.layout_ready_count == starter.page_count
    assert second.skipped_count == starter.page_count
