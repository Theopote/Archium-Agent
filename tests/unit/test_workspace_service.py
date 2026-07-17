"""Unit tests for Streamlit workspace service helpers."""

from __future__ import annotations

from archium.domain.enums import PresentationType, ProjectType
from archium.ui.workspace_service import (
    build_presentation_request,
    create_project,
    get_project_overview,
    list_projects,
)
from sqlalchemy.orm import Session


def test_create_project_and_overview(db_session: Session) -> None:
    project = create_project(
        db_session,
        name="测试项目",
        project_type=ProjectType.HEALTHCARE,
        description="说明",
    )
    db_session.commit()

    overview = get_project_overview(db_session, project.id)
    assert overview is not None
    assert overview.project.name == "测试项目"
    assert overview.document_count == 0
    assert overview.presentation_count == 0

    projects = list_projects(db_session)
    assert any(item.id == project.id for item in projects)


def test_build_presentation_request_parses_sections() -> None:
    request = build_presentation_request(
        title="概念汇报",
        audience="甲方",
        purpose="决策",
        core_message="核心结论",
        target_slide_count=8,
        required_sections_text="现状分析\n改造策略",
        presentation_type=PresentationType.CLIENT_REVIEW,
    )
    assert request.title == "概念汇报"
    assert request.required_sections == ["现状分析", "改造策略"]
    assert request.presentation_type == PresentationType.CLIENT_REVIEW


def test_build_presentation_request_supports_chinese_separator() -> None:
    request = build_presentation_request(
        title="汇报",
        audience="甲方",
        purpose="决策",
        core_message="核心结论",
        target_slide_count=6,
        required_sections_text="现状分析、改造策略",
    )
    assert request.required_sections == ["现状分析", "改造策略"]
