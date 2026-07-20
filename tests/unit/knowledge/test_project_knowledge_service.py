"""Unit tests for ProjectKnowledgeService."""

from __future__ import annotations

from archium.application.project_knowledge_service import ProjectKnowledgeService
from archium.domain.enums import (
    DocumentPurpose,
    InformationOrigin,
    InformationReliability,
    VerificationStatus,
)
from archium.domain.fact import ProjectFact
from archium.domain.project import Project
from archium.domain.project_knowledge import SourceCitation
from archium.infrastructure.database.repositories import (
    DocumentRepository,
    FactRepository,
    ProjectRepository,
)
from sqlalchemy.orm import Session


def _seed_project(db_session: Session) -> Project:
    return ProjectRepository(db_session).create(Project(name="Knowledge 测试"))


def test_knowledge_view_sections_separate_reference_and_inference(db_session: Session) -> None:
    project = _seed_project(db_session)
    FactRepository(db_session).create(
        ProjectFact(
            project_id=project.id,
            key="main_function",
            label="主要功能",
            value="文化展示",
            verification_status=VerificationStatus.INFERRED,
        )
    )
    service = ProjectKnowledgeService(db_session)
    service.create_item(
        project.id,
        statement="参考村落年游客量 10 万",
        origin=InformationOrigin.REFERENCE_CASE,
        reliability=InformationReliability.HIGH_CONFIDENCE,
    )

    view = service.get_view(project.id)
    section_keys = {section.key: section for section in view.sections}

    assert len(section_keys["inference"].items) == 1
    assert len(section_keys["reference"].items) == 1
    assert len(view.generation_eligible_items) == 0


def test_create_public_research_requires_citation_for_gap(db_session: Session) -> None:
    project = _seed_project(db_session)
    service = ProjectKnowledgeService(db_session)
    service.create_item(
        project.id,
        statement="某文旅政策要求",
        origin=InformationOrigin.PUBLIC_RESEARCH,
        reliability=InformationReliability.UNVERIFIED,
    )

    view = service.get_view(project.id)
    assert view.gap_report is not None
    assert any(gap.category == "uncited_external" for gap in view.gap_report.gaps)


def test_document_purpose_marks_reference_facts(db_session: Session) -> None:
    project = _seed_project(db_session)
    docs = DocumentRepository(db_session)
    from archium.domain.document import SourceDocument
    from archium.domain.enums import DocumentType, ProcessingStatus

    document = docs.create_document(
        SourceDocument(
            project_id=project.id,
            filename="参考案例.pdf",
            original_path="/tmp/ref.pdf",
            stored_path="/tmp/ref.pdf",
            file_type=DocumentType.PDF,
            file_hash="a" * 64,
            size_bytes=100,
            processing_status=ProcessingStatus.COMPLETED,
        )
    )
    ProjectKnowledgeService(db_session).set_document_purpose(
        document.id,
        DocumentPurpose.REFERENCE_CASE,
    )
    FactRepository(db_session).create(
        ProjectFact(
            project_id=project.id,
            key="site_area",
            label="用地面积",
            value="12",
            unit="公顷",
            verification_status=VerificationStatus.USER_CONFIRMED,
            source_citations=[
                SourceCitation(
                    document_id=document.id,
                    document_name=document.filename,
                ).to_citation()
            ],
        )
    )

    eligible = ProjectKnowledgeService(db_session).generation_eligible_facts(project.id)
    assert eligible == []


def test_confirm_knowledge_item(db_session: Session) -> None:
    project = _seed_project(db_session)
    service = ProjectKnowledgeService(db_session)
    item = service.create_item(
        project.id,
        statement="村庄始建于明代",
        origin=InformationOrigin.USER_UPLOAD,
        reliability=InformationReliability.HIGH_CONFIDENCE,
    )
    confirmed = service.confirm_item(item.id)
    assert confirmed.is_confirmed
    assert confirmed.reliability == InformationReliability.CONFIRMED
