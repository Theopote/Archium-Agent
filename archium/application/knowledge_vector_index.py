"""Index ProjectKnowledgeItem / DesignKnowledge into the project vector space."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.retrieval_credibility import score_knowledge_credibility
from archium.config.settings import Settings, get_settings
from archium.domain.architectural_chunk import ArchitecturalChunkType
from archium.domain.enums import KnowledgeItemStatus
from archium.domain.project_knowledge import ProjectKnowledgeItem
from archium.infrastructure.database.repositories import ProjectKnowledgeRepository
from archium.infrastructure.embeddings.base import EmbeddingProvider
from archium.infrastructure.embeddings.factory import create_embedding_provider
from archium.infrastructure.vector.chroma_store import ChromaVectorStore, VectorSearchHit
from archium.logging import get_logger

logger = get_logger(__name__, operation="knowledge_vector_index")

RECORD_TYPE_KNOWLEDGE = "knowledge_item"
RECORD_TYPE_CHUNK = "document_chunk"
# Sentinel document_id so document-delete cascades never wipe knowledge vectors.
_KNOWLEDGE_DOC_ID = UUID(int=0)


def knowledge_item_embed_text(item: ProjectKnowledgeItem) -> str:
    """Flatten structured design knowledge for embedding."""
    parts: list[str] = []
    dk = item.design_knowledge
    if dk is not None:
        for value in (
            dk.topic,
            dk.insight,
            dk.principle,
            dk.spatial_translation,
            dk.material_strategy,
            dk.project_link,
            dk.applicability,
        ):
            if value and str(value).strip():
                parts.append(str(value).strip())
        parts.extend(ev.strip() for ev in dk.evidence if ev and ev.strip())
    if item.statement.strip():
        parts.append(item.statement.strip())
    parts.append(f"category:{item.category}")
    parts.append(f"origin:{item.origin.value}")
    return "\n".join(parts)


def knowledge_architectural_type(item: ProjectKnowledgeItem) -> ArchitecturalChunkType:
    dk = item.design_knowledge
    if dk is None:
        return ArchitecturalChunkType.GENERAL
    if dk.spatial_translation.strip():
        return ArchitecturalChunkType.SPATIAL_STRATEGY
    if dk.material_strategy.strip():
        return ArchitecturalChunkType.MATERIAL_STRATEGY
    if dk.principle.strip() or dk.insight.strip():
        return ArchitecturalChunkType.DESIGN_CONCEPT
    if dk.topic.strip():
        return ArchitecturalChunkType.CASE_BACKGROUND
    return ArchitecturalChunkType.GENERAL


class KnowledgeVectorIndexService:
    """Upsert / query knowledge items in the same Chroma project collection."""

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
        self._knowledge = ProjectKnowledgeRepository(session)

    @property
    def available(self) -> bool:
        return bool(self._settings.retrieval_enabled and self._embedder is not None)

    def index_item(self, item: ProjectKnowledgeItem) -> None:
        if not self.available:
            return
        if item.status not in {KnowledgeItemStatus.ACTIVE, KnowledgeItemStatus.CONFIRMED}:
            self.remove_item(item.project_id, item.id)
            return
        self.index_items(item.project_id, [item])

    def index_items(self, project_id: UUID, items: list[ProjectKnowledgeItem]) -> None:
        if not self.available or not items:
            return
        assert self._embedder is not None
        active = [
            item
            for item in items
            if item.status in {KnowledgeItemStatus.ACTIVE, KnowledgeItemStatus.CONFIRMED}
        ]
        if not active:
            return
        texts = [knowledge_item_embed_text(item) for item in active]
        embeddings = self._embedder.embed_documents(texts)
        records = []
        for item, text in zip(active, texts, strict=True):
            cred = score_knowledge_credibility(item)
            arch = knowledge_architectural_type(item)
            records.append(
                {
                    "id": str(item.id),
                    "content": text,
                    "metadata": {
                        "chunk_id": str(item.id),
                        "document_id": str(_KNOWLEDGE_DOC_ID),
                        "project_id": str(project_id),
                        "page_number": 0,
                        "section_title": _knowledge_title(item),
                        "chunk_index": 0,
                        "document_name": "project_knowledge",
                        "content_type": "knowledge_item",
                        "architectural_type": arch.value,
                        "asset_id": "",
                        "record_type": RECORD_TYPE_KNOWLEDGE,
                        "reliability": item.reliability.value,
                        "authority": round(cred.authority, 4),
                        "transferability": round(cred.transferability, 4),
                        "origin": item.origin.value,
                    },
                }
            )
        self._store.upsert_records(project_id, records, embeddings)
        logger.info("Indexed %d knowledge items for project %s", len(records), project_id)

    def remove_item(self, project_id: UUID, item_id: UUID) -> None:
        if not self._settings.retrieval_enabled:
            return
        self._store.delete_ids(project_id, [str(item_id)])

    def reindex_project(self, project_id: UUID) -> int:
        items = [
            item
            for item in self._knowledge.list_by_project(project_id)
            if item.status in {KnowledgeItemStatus.ACTIVE, KnowledgeItemStatus.CONFIRMED}
        ]
        self.index_items(project_id, items)
        return len(items)

    def search(
        self,
        project_id: UUID,
        query: str,
        *,
        top_k: int = 8,
    ) -> list[VectorSearchHit]:
        if not self.available or not query.strip():
            return []
        assert self._embedder is not None
        hits = self._store.query(
            project_id,
            self._embedder.embed_query(query),
            top_k=max(top_k * 2, top_k),
            where={"record_type": RECORD_TYPE_KNOWLEDGE},
        )
        knowledge_hits = [hit for hit in hits if hit.record_type == RECORD_TYPE_KNOWLEDGE]
        if knowledge_hits:
            return knowledge_hits[:top_k]
        # Legacy collections without record_type filter — client filter by content_type
        open_hits = self._store.query(
            project_id,
            self._embedder.embed_query(query),
            top_k=max(top_k * 3, top_k),
            where=None,
        )
        return [
            hit
            for hit in open_hits
            if hit.record_type == RECORD_TYPE_KNOWLEDGE or hit.content_type == "knowledge_item"
        ][:top_k]


def best_effort_index_knowledge_item(session: Session, item: ProjectKnowledgeItem) -> None:
    """Never fail callers (research / UI) on vector index errors."""
    try:
        KnowledgeVectorIndexService(session).index_item(item)
    except Exception as exc:  # noqa: BLE001
        logger.warning("knowledge vector index failed for %s: %s", item.id, exc)


def _knowledge_title(item: ProjectKnowledgeItem) -> str:
    dk = item.design_knowledge
    if dk is not None and dk.topic.strip():
        return dk.topic.strip()[:200]
    return (item.category or "knowledge")[:200]
