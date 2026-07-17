"""Tests for semantic retrieval."""

from __future__ import annotations

from archium.application.retrieval_service import RetrievalService
from archium.domain.document import DocumentChunk, SourceDocument
from archium.domain.enums import DocumentType, ProcessingStatus, ProjectType
from archium.domain.project import Project
from archium.infrastructure.database.repositories import DocumentRepository, ProjectRepository
from archium.infrastructure.embeddings.mock import MockEmbeddingProvider
from archium.infrastructure.vector.chroma_store import ChromaVectorStore
from sqlalchemy.orm import Session


def _seed_chunks(db_session: Session) -> tuple[Project, list[DocumentChunk]]:
    project = ProjectRepository(db_session).create(
        Project(name="检索测试项目", project_type=ProjectType.HEALTHCARE)
    )
    repo = DocumentRepository(db_session)
    document = repo.create_document(
        SourceDocument(
            project_id=project.id,
            filename="任务书.pdf",
            original_path="/tmp/任务书.pdf",
            stored_path="/tmp/任务书.pdf",
            file_type=DocumentType.PDF,
            file_hash="b" * 64,
            size_bytes=1024,
            processing_status=ProcessingStatus.COMPLETED,
        )
    )
    chunks = [
        DocumentChunk(
            project_id=project.id,
            document_id=document.id,
            content="老院区交通组织混乱，人车混行严重，需优化流线。",
            page_number=1,
            section_title="现状",
            chunk_index=0,
        ),
        DocumentChunk(
            project_id=project.id,
            document_id=document.id,
            content="景观绿化以本地乔木为主，强调四季有景。",
            page_number=2,
            section_title="景观",
            chunk_index=1,
        ),
        DocumentChunk(
            project_id=project.id,
            document_id=document.id,
            content="结构体系采用钢筋混凝土框架，满足抗震设防要求。",
            page_number=3,
            section_title="结构",
            chunk_index=2,
        ),
    ]
    saved = [repo.create_chunk(chunk) for chunk in chunks]
    return project, saved


def test_retrieval_prefers_relevant_chunk(
    db_session: Session,
    test_settings: object,
) -> None:
    project, chunks = _seed_chunks(db_session)
    store = ChromaVectorStore(test_settings.chroma_path)  # type: ignore[attr-defined]
    service = RetrievalService(
        db_session,
        settings=test_settings,  # type: ignore[arg-type]
        embedder=MockEmbeddingProvider(),
        store=store,
    )

    service.index_chunks(project.id, chunks, document_name="任务书.pdf")
    results = service.retrieve(project.id, "老院区交通组织混乱 人车混行", top_k=1)

    assert len(results) == 1
    assert "交通组织" in results[0].content


def test_retrieval_falls_back_without_index(
    db_session: Session,
    test_settings: object,
) -> None:
    project, _ = _seed_chunks(db_session)
    service = RetrievalService(
        db_session,
        settings=test_settings,  # type: ignore[arg-type]
        embedder=MockEmbeddingProvider(),
        store=ChromaVectorStore(test_settings.chroma_path),  # type: ignore[attr-defined]
    )

    results = service.retrieve(project.id, "交通组织", top_k=2)
    assert len(results) == 2
    assert results[0].chunk_index <= results[1].chunk_index
