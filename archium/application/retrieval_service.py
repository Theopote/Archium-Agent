"""Semantic retrieval over project document chunks."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.retrieval_filters import RetrievalFilters
from archium.application.retrieval_hybrid import rerank_retrieved_chunks
from archium.config.settings import Settings, get_settings
from archium.domain.architectural_chunk import infer_types_from_query
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
        annotated = [chunk.ensure_architectural_annotation() for chunk in chunks]
        embeddings = self._embedder.embed_documents([chunk.content for chunk in annotated])
        self._store.upsert_chunks(
            project_id,
            annotated,
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
        filters: RetrievalFilters | None = None,
    ) -> list[DocumentChunk]:
        limit = top_k or self._settings.retrieval_top_k
        scoped = (filters or RetrievalFilters()).with_default_chunk_scope()
        if not self.available or not query.strip():
            return self._fallback_chunks(project_id, limit, filters=scoped)

        assert self._embedder is not None
        where = scoped.to_chroma_where() if not scoped.is_empty() else None
        # Over-fetch slightly when soft architectural preferences exist
        preferred = infer_types_from_query(query)
        fetch_k = limit * 2 if preferred and (
            filters is None or not filters.architectural_types
        ) else limit
        hits = self._store.query(
            project_id,
            self._embedder.embed_query(query),
            top_k=fetch_k,
            where=where,
        )
        hits = [h for h in hits if h.record_type != "knowledge_item"]
        if not hits:
            logger.info(
                "No vector hits for project %s; falling back to sequential chunks",
                project_id,
            )
            return self._fallback_chunks(project_id, limit, filters=scoped)

        chunk_ids = [hit.chunk_id for hit in hits]
        chunks = self._documents.get_chunks_by_ids(chunk_ids)
        if not chunks:
            return self._fallback_chunks(project_id, limit, filters=scoped)
        chunks = self._apply_client_filters(chunks, scoped)
        if self._settings.retrieval_keyword_boost_enabled:
            chunks = rerank_retrieved_chunks(
                chunks,
                hits,
                query,
                preferred_architectural_types=preferred,
            )
        return chunks[:limit]

    def search(
        self,
        project_id: UUID,
        query: str,
        *,
        top_k: int | None = None,
        filters: RetrievalFilters | None = None,
    ) -> list[VectorSearchHit]:
        limit = top_k or self._settings.retrieval_top_k
        if not self.available or not query.strip():
            return []
        assert self._embedder is not None
        scoped = (filters or RetrievalFilters()).with_default_chunk_scope()
        where = scoped.to_chroma_where() if not scoped.is_empty() else None
        hits = self._store.query(
            project_id,
            self._embedder.embed_query(query),
            top_k=limit,
            where=where,
        )
        hits = [h for h in hits if self._hit_matches_filters(h, scoped)]
        return hits

    def _fallback_chunks(
        self,
        project_id: UUID,
        limit: int,
        *,
        filters: RetrievalFilters | None = None,
    ) -> list[DocumentChunk]:
        chunks = self._documents.list_chunks_by_project(project_id)
        chunks = self._apply_client_filters(chunks, filters)
        return chunks[:limit]

    @staticmethod
    def _apply_client_filters(
        chunks: list[DocumentChunk],
        filters: RetrievalFilters | None,
    ) -> list[DocumentChunk]:
        if filters is None or filters.is_empty():
            return chunks
        result = chunks
        if filters.content_types:
            allowed = set(filters.content_types)
            result = [c for c in result if c.content_type in allowed]
        if filters.architectural_types:
            allowed_arch = {t.value for t in filters.architectural_types}
            result = [
                c
                for c in result
                if str(c.metadata.get("architectural_type") or c.architectural_type.value)
                in allowed_arch
            ]
        if filters.document_ids:
            allowed_docs = set(filters.document_ids)
            result = [c for c in result if c.document_id in allowed_docs]
        return result

    @staticmethod
    def _hit_matches_filters(hit: VectorSearchHit, filters: RetrievalFilters) -> bool:
        if filters.record_types and hit.record_type not in filters.record_types:
            return False
        if filters.content_types and hit.content_type not in filters.content_types:
            return False
        if filters.architectural_types:
            allowed = {t.value for t in filters.architectural_types}
            if hit.architectural_type not in allowed:
                return False
        return not (filters.document_ids and hit.document_id not in filters.document_ids)


def create_retrieval_service(
    session: Session,
    settings: Settings | None = None,
) -> RetrievalService:
    """Build a retrieval service from application settings."""
    return RetrievalService(session, settings=settings)
