"""Tests for DocumentRepository."""

from __future__ import annotations

from uuid import UUID

import pytest
from archium.domain.document import DocumentChunk, SourceDocument
from archium.domain.enums import DocumentType, ProcessingStatus, ProjectType
from archium.domain.project import Project
from archium.exceptions import RepositoryError
from archium.infrastructure.database.repositories import DocumentRepository, ProjectRepository
from sqlalchemy.orm import Session

SHA256_A = "a" * 64
SHA256_B = "b" * 64


@pytest.fixture
def project_id(db_session: Session) -> UUID:
    project = ProjectRepository(db_session).create(
        Project(name="测试项目", project_type=ProjectType.HEALTHCARE)
    )
    return project.id


@pytest.fixture
def doc_repo(db_session: Session) -> DocumentRepository:
    return DocumentRepository(db_session)


def _make_document(project_id: UUID, *, file_hash: str = SHA256_A) -> SourceDocument:
    return SourceDocument(
        project_id=project_id,
        filename="项目任务书.pdf",
        original_path="/uploads/项目任务书.pdf",
        stored_path=f"data/projects/{project_id}/sources/项目任务书.pdf",
        file_type=DocumentType.PDF,
        file_hash=file_hash,
        size_bytes=2048,
        page_count=12,
    )


def test_create_and_get_document(doc_repo: DocumentRepository, project_id: UUID) -> None:
    doc = doc_repo.create_document(_make_document(project_id))
    fetched = doc_repo.get_document(doc.id)
    assert fetched is not None
    assert fetched.filename == "项目任务书.pdf"
    assert fetched.page_count == 12


def test_list_documents_by_project(doc_repo: DocumentRepository, project_id: UUID) -> None:
    doc_repo.create_document(_make_document(project_id, file_hash=SHA256_A))
    doc_repo.create_document(_make_document(project_id, file_hash=SHA256_B))
    docs = doc_repo.list_by_project(project_id)
    assert len(docs) == 2


def test_duplicate_hash_rejected(doc_repo: DocumentRepository, project_id: UUID) -> None:
    doc_repo.create_document(_make_document(project_id))
    with pytest.raises(RepositoryError, match="Duplicate"):
        doc_repo.create_document(_make_document(project_id))


def test_get_by_hash(doc_repo: DocumentRepository, project_id: UUID) -> None:
    doc_repo.create_document(_make_document(project_id))
    found = doc_repo.get_by_hash(project_id, SHA256_A)
    assert found is not None
    assert found.file_hash == SHA256_A


def test_update_document_status(doc_repo: DocumentRepository, project_id: UUID) -> None:
    doc = doc_repo.create_document(_make_document(project_id))
    doc.mark_completed(page_count=15)
    updated = doc_repo.update_document(doc)
    assert updated.processing_status == ProcessingStatus.COMPLETED
    assert updated.page_count == 15


def test_create_and_list_chunks(doc_repo: DocumentRepository, project_id: UUID) -> None:
    doc = doc_repo.create_document(_make_document(project_id))
    chunk = DocumentChunk(
        project_id=project_id,
        document_id=doc.id,
        content="院区现状存在交通组织混乱问题。",
        page_number=2,
        chunk_index=0,
    )
    created = doc_repo.create_chunk(chunk)
    chunks = doc_repo.list_chunks(doc.id)
    assert len(chunks) == 1
    assert chunks[0].id == created.id
    assert chunks[0].content == chunk.content


def test_delete_document(doc_repo: DocumentRepository, project_id: UUID) -> None:
    doc = doc_repo.create_document(_make_document(project_id))
    assert doc_repo.delete_document(doc.id) is True
    assert doc_repo.get_document(doc.id) is None
