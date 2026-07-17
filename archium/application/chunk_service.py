"""Manage document chunk edits and vector re-indexing."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.retrieval_service import RetrievalService, create_retrieval_service
from archium.config.settings import Settings, get_settings
from archium.domain.document import DocumentChunk
from archium.exceptions import RepositoryError
from archium.infrastructure.database.repositories import DocumentRepository


class ChunkService:
    """Read and update persisted document chunks."""

    def __init__(
        self,
        session: Session,
        *,
        settings: Settings | None = None,
        retrieval: RetrievalService | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._documents = DocumentRepository(session)
        self._retrieval = retrieval or create_retrieval_service(session, self._settings)

    def list_document_chunks(self, document_id: UUID) -> list[DocumentChunk]:
        return self._documents.list_chunks(document_id)

    def list_project_chunks(self, project_id: UUID) -> list[DocumentChunk]:
        return self._documents.list_chunks_by_project(project_id)

    def update_chunk(
        self,
        chunk_id: UUID,
        *,
        content: str,
        section_title: str | None = None,
    ) -> DocumentChunk:
        chunk = self._documents.get_chunk(chunk_id)
        if chunk is None:
            raise RepositoryError(f"Chunk {chunk_id} not found")

        normalized = content.strip()
        if not normalized:
            raise ValueError("chunk content must not be empty")

        chunk.content = normalized
        if section_title is not None:
            chunk.section_title = section_title.strip() or None
        chunk.metadata = {
            **chunk.metadata,
            "manually_edited": True,
        }
        updated = self._documents.update_chunk(chunk)

        document = self._documents.get_document(updated.document_id)
        document_name = document.filename if document is not None else ""
        try:
            self._retrieval.index_chunks(
                updated.project_id,
                [updated],
                document_name=document_name,
            )
        except Exception:
            pass
        return updated
