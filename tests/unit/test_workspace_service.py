"""Unit tests for Streamlit workspace service helpers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from archium.application.ingestion_service import ImportItemResult
from archium.config.settings import Settings
from archium.domain.enums import PresentationType, ProjectType
from archium.ui.workspace_service import (
    build_presentation_request,
    create_project,
    get_project_overview,
    import_uploaded_file,
    list_projects,
    resolve_generation_form_defaults,
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


def test_resolve_generation_form_defaults_from_genesis_outline(db_session: Session) -> None:
    from archium.application.genesis_starter_service import ensure_genesis_starter_draft
    from archium.domain.project import Project
    from archium.infrastructure.database.repositories import ProjectRepository

    project = ProjectRepository(db_session).create(
        Project(name="陕西三原县清凉寺重建验证", description="寺庙原址重建")
    )
    db_session.commit()
    starter = ensure_genesis_starter_draft(
        db_session,
        project.id,
        prompt="陕西三原县清凉寺历史上多次被毁坏，要在原址重建，投资2亿元。",
        project_name=project.name,
    )
    db_session.commit()
    defaults = resolve_generation_form_defaults(db_session, project.id)
    assert "清凉寺" in defaults.title
    assert defaults.audience
    assert defaults.purpose
    assert defaults.core_message
    assert defaults.target_slide_count == starter.page_count
    assert "背景" in defaults.sections or "封面" in defaults.sections


def test_import_uploaded_file_triggers_reassess(
    db_session: Session, test_settings: Settings
) -> None:
    from pathlib import Path

    project = create_project(db_session, name="上传后刷新", project_type=ProjectType.HEALTHCARE)
    db_session.commit()
    fake_result = ImportItemResult(source_path=Path("brief.pdf"))
    with (
        patch(
            "archium.application.api.documents.DocumentsApi.upload_file",
            return_value=fake_result,
        ),
        patch(
            "archium.application.context.best_effort_reassess_knowledge"
        ) as reassess,
        patch(
            "archium.infrastructure.llm.factory.create_llm_provider",
            return_value=MagicMock(),
        ),
    ):
        result = import_uploaded_file(
            db_session,
            project.id,
            filename="brief.pdf",
            data=b"%PDF-1.4 fake",
            settings=test_settings,
        )
    assert result is fake_result
    assert reassess.call_count == 1
    assert reassess.call_args.args[1] == project.id


def test_import_uploaded_file_can_skip_reassess(
    db_session: Session, test_settings: Settings
) -> None:
    from pathlib import Path

    project = create_project(db_session, name="批量跳过", project_type=ProjectType.HEALTHCARE)
    db_session.commit()
    fake_result = ImportItemResult(source_path=Path("a.pdf"))
    with (
        patch(
            "archium.application.api.documents.DocumentsApi.upload_file",
            return_value=fake_result,
        ),
        patch(
            "archium.application.context.best_effort_reassess_knowledge"
        ) as reassess,
    ):
        import_uploaded_file(
            db_session,
            project.id,
            filename="a.pdf",
            data=b"%PDF",
            reassess=False,
            settings=test_settings,
        )
    reassess.assert_not_called()


def test_reassess_knowledge_after_upload_builds_tip(
    db_session: Session, test_settings: Settings
) -> None:
    from archium.application.context_intelligence_service import ContextAssessment
    from archium.domain.intent.knowledge_state import KnowledgeState
    from archium.domain.intent.next_best_action import NextBestAction, NextBestActionType
    from archium.ui.workspace_service import reassess_knowledge_after_upload

    project = create_project(db_session, name="提示卡片", project_type=ProjectType.HEALTHCARE)
    db_session.commit()
    fake = ContextAssessment(
        knowledge_state=KnowledgeState(
            completeness_score=0.42,
            evidence_ratio=0.3,
            assumption_ratio=0.6,
            missing_information=["投资规模", "使用人群"],
        ),
        actions=[
            NextBestAction(
                action=NextBestActionType.UPLOAD_MATERIALS,
                reason="继续补资料",
                priority=0,
            ),
            NextBestAction(
                action=NextBestActionType.EXPLORE_DIRECTIONS,
                reason="可开始推演",
                priority=1,
            ),
        ],
        understanding_summary="资料增加后，地点与类型更清晰。",
    )
    with (
        patch(
            "archium.application.context.best_effort_reassess_knowledge",
            return_value=fake,
        ),
        patch(
            "archium.infrastructure.llm.factory.create_llm_provider",
            return_value=MagicMock(),
        ),
    ):
        tip = reassess_knowledge_after_upload(
            db_session, project.id, settings=test_settings
        )

    assert tip is not None
    assert "30%" in tip.summary_line  # evidence_ratio via summary_line bits
    assert tip.understanding_summary.startswith("资料增加")
    assert tip.primary_action == "explore_directions"
    assert tip.primary_action_label == "开始推演方向"
    assert any("推演" in label for label in tip.next_action_labels)


def test_import_uploaded_file_survives_reassess_failure(
    db_session: Session, test_settings: Settings
) -> None:
    from pathlib import Path

    project = create_project(db_session, name="上传容错", project_type=ProjectType.HEALTHCARE)
    db_session.commit()
    fake_result = ImportItemResult(source_path=Path("site.jpg"))
    with (
        patch(
            "archium.application.api.documents.DocumentsApi.upload_file",
            return_value=fake_result,
        ),
        patch(
            "archium.application.context.best_effort_reassess_knowledge",
            return_value=None,
        ),
        patch(
            "archium.infrastructure.llm.factory.create_llm_provider",
            return_value=MagicMock(),
        ),
    ):
        result = import_uploaded_file(
            db_session,
            project.id,
            filename="site.jpg",
            data=b"fake-image",
            settings=test_settings,
        )
    assert result.error is None
