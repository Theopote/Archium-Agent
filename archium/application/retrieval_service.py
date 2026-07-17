"""Semantic retrieval over project document chunks."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.config.settings import Settings, get_settings
from archium.domain.document import DocumentChunk
from archium.infrastructure.database.repositories import DocumentRepository
from archium.infrastructure.embeddings.base import EmbeddingProvider
from archium.infrastructure.embeddings.factory import create_embedding_provider
from archium.infrastructure.vector.chroma_store import ChromaVectorStore, VectorSearchHit
from archium.logging import get_logger

logger = get_logger(__name__, operation="retrieval")


class RetrievalService:
    """Index and retrieve document chunks for presentation generation."""

    def __init__(
        self,
        session: Session,
        *,
        settings: Settings | None = None,
        embedder: EmbeddingProvider | None = None,
        store: ChromaVectorStore | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._embedder = embedder if embedder is not None else create_embedding_provider(self._settings)
        self._store = store or ChromaVectorStore(self._settings.chroma_path)
        self._documents = DocumentRepository(session)

    @property
    def available(self) -> bool:
        return self._settings.retrieval_enabled and self._embedder is not None

    def index_chunks(
        self,
        project_id: UUID,
        chunks: list[DocumentChunk],
        *,
        document_name: str = "",
    ) -> None:
        if not self.available or not chunks:
            return
        assert self._embedder is not None
        embeddings = self._embedder.embed_documents([chunk.content for chunk in chunks])
        self._store.upsert_chunks(
            project_id,
            chunks,
            embeddings,
            document_name=document_name,
        )

    def remove_document(self, project_id: UUID, document_id: UUID) -> None:
        if not self._settings.retrieval_enabled:
            return
        self._store.delete_document(project_id, document_id)

    def retrieve(
        self,
        project_id: UUID,
        query: str,
        *,
        top_k: int | None = None,
    ) -> list[DocumentChunk]:
        limit = top_k or self._settings.retrieval_top_k
        if not self.available or not query.strip():
            return self._fallback_chunks(project_id, limit)

        assert self._embedder is not None
        hits = self._store.query(
            project_id,
            self._embedder.embed_query(query),
            top_k=limit,
        )
        if not hits:
            logger.info(
                "No vector hits for project %s; falling back to sequential chunks",
                project_id,
            )
            return self._fallback_chunks(project_id, limit)

        chunk_ids = [hit.chunk_id for hit in hits]
        chunks = self._documents.get_chunks_by_ids(chunk_ids)
        if not chunks:
            return self._fallback_chunks(project_id, limit)
        return chunks

    def search(
        self,
        project_id: UUID,
        query: str,
        *,
        top_k: int | None = None,
    ) -> list[VectorSearchHit]:
        limit = top_k or self._settings.retrieval_top_k
        if not self.available or not query.strip():
            return []
        assert self._embedder is not None
        return self._store.query(
            project_id,
            self._embedder.embed_query(query),
            top_k=limit,
        )

    def _fallback_chunks(self, project_id: UUID, limit: int) -> list[DocumentChunk]:
        return self._documents.list_chunks_by_project(project_id)[:limit]


def create_retrieval_service(
    session: Session,
    settings: Settings | None = None,
) -> RetrievalService:
    """Build a retrieval service from application settings."""
    return RetrievalService(session, settings=settings)
