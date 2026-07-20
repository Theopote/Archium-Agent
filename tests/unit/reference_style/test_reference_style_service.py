"""Unit tests for reference style profile extraction."""

from __future__ import annotations

from uuid import uuid4

from archium.application.reference_style_service import (
    profile_fallback_from_brief,
    profile_from_draft,
    validate_reference_style_profile,
)
from archium.domain.enums import DocumentPurpose
from archium.domain.document import SourceDocument
from archium.domain.presentation import PresentationBrief
from archium.infrastructure.llm.presentation_schemas import ReferenceStyleProfileDraft


def _brief() -> PresentationBrief:
    return PresentationBrief(
        project_id=uuid4(),
        presentation_id=uuid4(),
        title="改造汇报",
        audience="甲方",
        purpose="老旧建筑改造",
        core_message="提升品质",
    )


def test_profile_from_draft_maps_style_fields() -> None:
    project_id = uuid4()
    draft = ReferenceStyleProfileDraft(
        style_name="测试风格",
        mood_keywords=["克制"],
        do_rules=["保持层级"],
        dont_rules=["过度装饰"],
    )
    profile = profile_from_draft(
        draft,
        project_id=project_id,
        source_document_ids=["doc1"],
    )
    assert profile.project_id == project_id
    assert profile.style_name == "测试风格"
    assert profile.source_document_ids == ["doc1"]


def test_validate_reference_style_profile_flags_missing_sources() -> None:
    profile = profile_from_draft(
        ReferenceStyleProfileDraft(style_name="风格"),
        project_id=uuid4(),
        source_document_ids=[],
    )
    issues = validate_reference_style_profile(profile)
    assert any("未关联参考风格文件" in issue for issue in issues)


def test_profile_fallback_from_brief() -> None:
    brief = _brief()
    profile = profile_fallback_from_brief(
        brief,
        project_id=brief.project_id,
        source_document_ids=["doc1"],
    )
    assert profile.do_rules
    assert profile.dont_rules
    assert "doc1" in profile.source_document_ids


def test_list_reference_style_documents_filters_purpose(db_session) -> None:
    from archium.application.reference_style_service import list_reference_style_documents
    from archium.infrastructure.database.repositories import DocumentRepository, ProjectRepository
    from archium.domain.project import Project

    project = ProjectRepository(db_session).create(Project(name="Style Test"))
    repo = DocumentRepository(db_session)
    repo.create_document(
        SourceDocument(
            project_id=project.id,
            filename="style-ref.pptx",
            original_path="/tmp/style-ref.pptx",
            stored_path="/tmp/style-ref.pptx",
            file_type="pptx",
            file_hash="a" * 64,
            size_bytes=100,
            metadata={"purpose": DocumentPurpose.REFERENCE_STYLE.value},
        )
    )
    repo.create_document(
        SourceDocument(
            project_id=project.id,
            filename="project.pdf",
            original_path="/tmp/project.pdf",
            stored_path="/tmp/project.pdf",
            file_type="pdf",
            file_hash="b" * 64,
            size_bytes=100,
            metadata={"purpose": DocumentPurpose.PROJECT_MATERIAL.value},
        )
    )
    style_docs = list_reference_style_documents(db_session, project.id)
    assert len(style_docs) == 1
    assert style_docs[0].filename == "style-ref.pptx"
