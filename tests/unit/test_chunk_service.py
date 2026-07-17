"""Unit tests for chunk edit service."""

from __future__ import annotations

from archium.application.chunk_service import ChunkService
from archium.domain.document import DocumentChunk, SourceDocument
from archium.domain.enums import DocumentType, ProcessingStatus, ProjectType
from archium.domain.project import Project
from archium.infrastructure.database.repositories import DocumentRepository, ProjectRepository
from archium.infrastructure.embeddings.mock import MockEmbeddingProvider
from archium.infrastructure.vector.chroma_store import ChromaVectorStore
from sqlalchemy.orm import Session


def test_update_chunk_persists_and_reindexes(db_session: Session, test_settings: object) -> None:
    project = ProjectRepository(db_session).create(
        Project(name="片段编辑", project_type=ProjectType.HEALTHCARE)
    )
    repo = DocumentRepository(db_session)
    document = repo.create_document(
        SourceDocument(
            project_id=project.id,
            filename="资料.pdf",
            original_path="/tmp/资料.pdf",
            stored_path="/tmp/资料.pdf",
            file_type=DocumentType.PDF,
            file_hash="e" * 64,
            size_bytes=1024,
            processing_status=ProcessingStatus.COMPLETED,
        )
    )
    chunk = repo.create_chunk(
        DocumentChunk(
            project_id=project.id,
            document_id=document.id,
            content="原始片段内容。",
            page_number=1,
            chunk_index=0,
        )
    )
    store = ChromaVectorStore(test_settings.chroma_path)  # type: ignore[attr-defined]
    from archium.application.retrieval_service import RetrievalService

    service = ChunkService(
        db_session,
        settings=test_settings,  # type: ignore[arg-type]
        retrieval=RetrievalService(
            db_session,
            settings=test_settings,  # type: ignore[arg-type]
            embedder=MockEmbeddingProvider(),
            store=store,
        ),
    )
    service._retrieval.index_chunks(project.id, [chunk], document_name=document.filename)

    updated = service.update_chunk(chunk.id, content="更新后的片段内容。")
    assert updated.content == "更新后的片段内容。"
    assert updated.metadata.get("manually_edited") is True

    hits = service._retrieval.search(project.id, "更新后的片段", top_k=1)
    assert hits
    assert hits[0].chunk_id == chunk.id
