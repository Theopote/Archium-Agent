"""Tests for query-aware project context building."""

from __future__ import annotations

from archium.agents._helpers import build_project_context, build_retrieval_query_from_request
from archium.application.presentation_models import PresentationRequest
from archium.application.retrieval_service import RetrievalService
from archium.domain.document import DocumentChunk, SourceDocument
from archium.domain.enums import DocumentType, ProcessingStatus, ProjectType
from archium.domain.project import Project
from archium.infrastructure.database.repositories import DocumentRepository, ProjectRepository
from archium.infrastructure.embeddings.mock import MockEmbeddingProvider
from archium.infrastructure.vector.chroma_store import ChromaVectorStore
from sqlalchemy.orm import Session


def test_build_project_context_uses_retrieval_query(
    db_session: Session,
    test_settings: object,
) -> None:
    project = ProjectRepository(db_session).create(
        Project(name="上下文测试", project_type=ProjectType.HEALTHCARE)
    )
    repo = DocumentRepository(db_session)
    document = repo.create_document(
        SourceDocument(
            project_id=project.id,
            filename="资料.pdf",
            original_path="/tmp/资料.pdf",
            stored_path="/tmp/资料.pdf",
            file_type=DocumentType.PDF,
            file_hash="c" * 64,
            size_bytes=1024,
            processing_status=ProcessingStatus.COMPLETED,
        )
    )
    chunks = [
        repo.create_chunk(
            DocumentChunk(
                project_id=project.id,
                document_id=document.id,
                content="停车系统不足，高峰期排队严重。",
                page_number=1,
                chunk_index=0,
            )
        ),
        repo.create_chunk(
            DocumentChunk(
                project_id=project.id,
                document_id=document.id,
                content="门诊大厅自然采光良好，空间通透。",
                page_number=2,
                chunk_index=1,
            )
        ),
    ]
    store = ChromaVectorStore(test_settings.chroma_path)  # type: ignore[attr-defined]
    RetrievalService(
        db_session,
        settings=test_settings,  # type: ignore[arg-type]
        embedder=MockEmbeddingProvider(),
        store=store,
    ).index_chunks(project.id, chunks)

    request = PresentationRequest(
        title="停车改造汇报",
        audience="后勤部门",
        purpose="确认停车扩容方案",
        duration_minutes=15,
        target_slide_count=4,
        required_sections=["停车现状"],
        user_notes="重点分析停车排队问题",
    )
    context = build_project_context(
        db_session,
        project.id,
        query=build_retrieval_query_from_request(request),
        settings=test_settings,  # type: ignore[arg-type]
        max_chunks=1,
    )

    assert "停车" in context
    assert "采光" not in context
