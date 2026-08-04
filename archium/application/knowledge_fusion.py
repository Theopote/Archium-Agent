"""Project Knowledge Space fusion — Fact + Chunk + KnowledgeItem (+ optional cases).

Not a new Agent: Service ranks KnowledgeReference with credibility dimensions
and optional vector hits from KnowledgeVectorIndexService.
"""

from __future__ import annotations

from uuid import UUID

from archium.application.architecture_case_library import ArchitectureCaseLibraryService
from archium.application.fact_retrieval import match_fact_keys_from_query, rank_facts_for_context
from archium.application.knowledge_isolation import filter_generation_facts, is_reference_document
from archium.application.knowledge_vector_index import (
    KnowledgeVectorIndexService,
    knowledge_architectural_type,
    knowledge_item_embed_text,
)
from archium.application.retrieval_credibility import (
    rank_relevance,
    score_chunk_credibility,
    score_fact_credibility,
    score_knowledge_credibility,
)
from archium.application.retrieval_filters import RetrievalFilters
from archium.application.retrieval_hybrid import keyword_overlap_score
from archium.application.retrieval_service import create_retrieval_service
from archium.application.unit_of_work import SessionLike, session_of
from archium.config.settings import Settings, get_settings
from archium.domain.architectural_chunk import (
    ArchitecturalChunkType,
    architectural_type_from_metadata,
    classify_architectural_chunk,
    infer_types_from_query,
)
from archium.domain.document import DocumentChunk
from archium.domain.enums import KnowledgeItemStatus, VerificationStatus
from archium.domain.fact import ProjectFact
from archium.domain.knowledge_reference import (
    KnowledgeReference,
    KnowledgeSourceKind,
    KnowledgeUsage,
)
from archium.domain.project_knowledge import ProjectKnowledgeItem
from archium.infrastructure.database.repositories import (
    DocumentRepository,
    FactRepository,
    ProjectKnowledgeRepository,
)
from archium.infrastructure.vector.chroma_store import VectorSearchHit


class KnowledgeFusionService:
    """Hybrid assemble of project-internal + external-structured knowledge hits."""

    def __init__(
        self,
        session: SessionLike,
        *,
        settings: Settings | None = None,
    ) -> None:
        session = session_of(session)
        self._session = session
        self._settings = settings or get_settings()
        self._facts = FactRepository(session)
        self._knowledge = ProjectKnowledgeRepository(session)
        self._documents = DocumentRepository(session)

    def retrieve(
        self,
        project_id: UUID,
        query: str,
        *,
        top_k: int = 16,
        filters: RetrievalFilters | None = None,
        include_cases: bool = True,
        include_graph: bool = True,
        include_multimodal: bool = True,
    ) -> list[KnowledgeReference]:
        query = (query or "").strip()
        preferred = infer_types_from_query(query)
        refs: list[KnowledgeReference] = []
        refs.extend(self._fact_refs(project_id, query))
        refs.extend(self._chunk_refs(project_id, query, filters=filters, preferred=preferred))
        refs.extend(self._knowledge_item_refs(project_id, query, preferred=preferred))
        if include_cases and query:
            refs.extend(self._case_refs(project_id, query))
        if include_graph and query and bool(
            getattr(self._settings, "knowledge_graph_retrieval_enabled", True)
        ):
            try:
                from archium.application.knowledge_graph_service import KnowledgeGraphService

                refs.extend(
                    KnowledgeGraphService(
                        self._session, settings=self._settings
                    ).retrieve_via_graph(project_id, query, top_k=max(6, top_k // 2))
                )
            except Exception:
                pass
        if include_multimodal and query and bool(
            getattr(self._settings, "multimodal_retrieval_enabled", True)
        ):
            try:
                from archium.application.multimodal_retrieval import MultimodalRetrievalService

                refs.extend(
                    MultimodalRetrievalService(
                        self._session, settings=self._settings
                    ).retrieve(project_id, query, top_k=max(4, top_k // 3))
                )
            except Exception:
                pass
        refs.sort(key=lambda item: item.relevance, reverse=True)
        return self._dedupe_refs(refs)[: max(1, top_k)]

    @staticmethod
    def _dedupe_refs(refs: list[KnowledgeReference]) -> list[KnowledgeReference]:
        seen: set[tuple[str, str]] = set()
        out: list[KnowledgeReference] = []
        for ref in refs:
            key = (ref.source_kind.value, ref.source_id)
            if key in seen:
                continue
            seen.add(key)
            out.append(ref)
        return out

    def format_prompt_block(self, refs: list[KnowledgeReference]) -> str:
        if not refs:
            return ""
        lines = ["【项目知识空间 · KnowledgeReference】"]
        lines.extend(ref.to_prompt_line() for ref in refs)
        return "\n".join(lines)

    def _fact_refs(self, project_id: UUID, query: str) -> list[KnowledgeReference]:
        all_facts = self._facts.list_by_project(project_id)
        reference_doc_ids = {
            str(doc.id)
            for doc in self._documents.list_by_project(project_id)
            if is_reference_document(doc.metadata or {})
        }
        active = filter_generation_facts(
            [
                fact
                for fact in all_facts
                if fact.verification_status != VerificationStatus.REJECTED
            ],
            reference_document_ids=reference_doc_ids or None,
        )
        ranked = rank_facts_for_context(active, query=query, limit=20)
        query_keys = match_fact_keys_from_query(query)
        refs: list[KnowledgeReference] = []
        for fact in ranked:
            similarity = 0.85 if fact.key in query_keys else (0.55 if query else 0.4)
            if query and keyword_overlap_score(query, f"{fact.label} {fact.value}") > 0.3:
                similarity = max(similarity, 0.7)
            cred = score_fact_credibility(fact)
            refs.append(
                KnowledgeReference(
                    source_kind=KnowledgeSourceKind.FACT,
                    source_id=str(fact.id),
                    content=self._format_fact(fact),
                    title=fact.label,
                    similarity=similarity,
                    authority=cred.authority,
                    transferability=cred.transferability,
                    relevance=rank_relevance(
                        similarity=similarity,
                        authority=cred.authority,
                        transferability=cred.transferability,
                        usage=KnowledgeUsage.EVIDENCE,
                        has_citations=cred.has_citations,
                    ),
                    usage=KnowledgeUsage.EVIDENCE,
                    project_id=project_id,
                    extra={"fact_key": fact.key},
                )
            )
        return refs

    def _chunk_refs(
        self,
        project_id: UUID,
        query: str,
        *,
        filters: RetrievalFilters | None,
        preferred: list[ArchitecturalChunkType],
    ) -> list[KnowledgeReference]:
        retrieval = create_retrieval_service(self._session, self._settings)
        hits: list[VectorSearchHit] = []
        chunks: list[DocumentChunk] = []
        if query and retrieval.available:
            hits = retrieval.search(
                project_id,
                query,
                top_k=self._settings.retrieval_top_k,
                filters=filters,
            )
            # Drop knowledge vectors that slipped through legacy collections
            hits = [h for h in hits if h.record_type != "knowledge_item"]
            if hits:
                by_id = {
                    chunk.id: chunk
                    for chunk in self._documents.get_chunks_by_ids([h.chunk_id for h in hits])
                }
                chunks = [by_id[h.chunk_id] for h in hits if h.chunk_id in by_id]
            else:
                chunks = retrieval.retrieve(
                    project_id, query, top_k=self._settings.retrieval_top_k, filters=filters
                )
        else:
            chunks = self._documents.list_chunks_by_project(project_id)[: self._settings.retrieval_top_k]

        hit_by_id = {hit.chunk_id: hit for hit in hits}
        refs: list[KnowledgeReference] = []
        for chunk in chunks:
            arch = architectural_type_from_metadata(chunk.metadata)
            if arch == ArchitecturalChunkType.GENERAL and not chunk.metadata.get(
                "architectural_type"
            ):
                arch = classify_architectural_chunk(
                    chunk.content,
                    section_title=chunk.section_title,
                    content_type=chunk.content_type,
                ).chunk_type
            hit = hit_by_id.get(chunk.id)
            similarity = hit.score if hit is not None else None
            if similarity is None:
                similarity = keyword_overlap_score(query, chunk.content) if query else 0.3
            if preferred and arch in preferred:
                similarity = min(1.0, float(similarity) + 0.12)
            cred = score_chunk_credibility(chunk, preferred_types=preferred)
            if hit is not None:
                # Prefer stored credibility when indexed with P1 metadata
                if hit.authority > 0:
                    cred_authority = max(cred.authority, hit.authority)
                else:
                    cred_authority = cred.authority
                if hit.transferability > 0:
                    cred_xfer = max(cred.transferability, hit.transferability)
                else:
                    cred_xfer = cred.transferability
            else:
                cred_authority = cred.authority
                cred_xfer = cred.transferability
            usage = (
                KnowledgeUsage.ILLUSTRATIVE
                if chunk.content_type == "asset_caption"
                else KnowledgeUsage.EVIDENCE
            )
            refs.append(
                KnowledgeReference(
                    source_kind=KnowledgeSourceKind.DOCUMENT_CHUNK,
                    source_id=str(chunk.id),
                    content=chunk.content[:1500],
                    title=(chunk.section_title or "文档片段")[:120],
                    similarity=float(similarity),
                    authority=cred_authority,
                    transferability=cred_xfer,
                    relevance=rank_relevance(
                        similarity=float(similarity),
                        authority=cred_authority,
                        transferability=cred_xfer,
                        usage=usage,
                        has_citations=cred.has_citations,
                    ),
                    usage=usage,
                    architectural_type=arch,
                    project_id=project_id,
                    extra={"content_type": chunk.content_type, "document_id": str(chunk.document_id)},
                )
            )
        return refs

    def _knowledge_item_refs(
        self,
        project_id: UUID,
        query: str,
        *,
        preferred: list[ArchitecturalChunkType],
    ) -> list[KnowledgeReference]:
        items = [
            item
            for item in self._knowledge.list_by_project(project_id)
            if item.status
            in {KnowledgeItemStatus.ACTIVE, KnowledgeItemStatus.CONFIRMED}
        ]
        by_id = {item.id: item for item in items}
        vector_scores: dict[UUID, float] = {}
        if query:
            try:
                for hit in KnowledgeVectorIndexService(
                    self._session, settings=self._settings
                ).search(project_id, query, top_k=max(8, self._settings.retrieval_top_k)):
                    if hit.chunk_id in by_id:
                        vector_scores[hit.chunk_id] = float(hit.score)
            except Exception:
                vector_scores = {}

        refs: list[KnowledgeReference] = []
        for item in items:
            text = knowledge_item_embed_text(item)
            lexical = keyword_overlap_score(query, text) if query else 0.35
            vector = vector_scores.get(item.id)
            if vector is not None:
                similarity = max(lexical, vector)
                # Blend: vector carries semantic match for design knowledge
                similarity = (0.55 * vector) + (0.45 * max(lexical, 0.15))
            else:
                similarity = lexical
            if similarity < 0.12 and query and item.id not in vector_scores:
                continue
            cred = score_knowledge_credibility(item, preferred_types=preferred)
            usage = (
                KnowledgeUsage.DESIGN_JUDGMENT
                if item.design_knowledge is not None and item.design_knowledge.has_substance
                else KnowledgeUsage.BACKGROUND
            )
            arch = knowledge_architectural_type(item)
            refs.append(
                KnowledgeReference(
                    source_kind=KnowledgeSourceKind.KNOWLEDGE_ITEM,
                    source_id=str(item.id),
                    content=text[:1500],
                    title=_knowledge_title(item),
                    similarity=max(0.15, similarity),
                    authority=cred.authority,
                    transferability=cred.transferability,
                    relevance=rank_relevance(
                        similarity=max(0.15, similarity),
                        authority=cred.authority,
                        transferability=cred.transferability,
                        usage=usage,
                        has_citations=cred.has_citations,
                    ),
                    usage=usage,
                    architectural_type=arch if arch != ArchitecturalChunkType.GENERAL else None,
                    project_id=project_id,
                    extra={
                        "origin": item.origin.value,
                        "reliability": item.reliability.value,
                        "vector_hit": item.id in vector_scores,
                    },
                )
            )
        return refs

    def _case_refs(self, project_id: UUID, query: str) -> list[KnowledgeReference]:
        library = ArchitectureCaseLibraryService(
            session=self._session,
            project_id=project_id,
            include_drafts=True,
        )
        cases = library.search(query, limit=2)
        refs: list[KnowledgeReference] = []
        for match in cases:
            case = match.case
            text = case.to_prompt_block()
            similarity = max(float(match.score), keyword_overlap_score(query, text))
            authority = 0.78
            transferability = 0.72 if case.transferable_principles else 0.48
            refs.append(
                KnowledgeReference(
                    source_kind=KnowledgeSourceKind.ARCHITECTURE_CASE,
                    source_id=case.id,
                    content=text[:1500],
                    title=case.name,
                    similarity=max(0.25, similarity),
                    authority=authority,
                    transferability=transferability,
                    relevance=rank_relevance(
                        similarity=max(0.25, similarity),
                        authority=authority,
                        transferability=transferability,
                        usage=KnowledgeUsage.ILLUSTRATIVE,
                        has_citations=False,
                    ),
                    usage=KnowledgeUsage.ILLUSTRATIVE,
                    architectural_type=ArchitecturalChunkType.CASE_BACKGROUND,
                    extra={"tags": list(case.tags)[:8], "matched_terms": list(match.matched_terms)},
                )
            )
        return refs

    @staticmethod
    def _format_fact(fact: ProjectFact) -> str:
        unit = f" {fact.unit}" if fact.unit else ""
        return f"{fact.label}: {fact.value}{unit}"


def _knowledge_title(item: ProjectKnowledgeItem) -> str:
    dk = item.design_knowledge
    if dk is not None and dk.topic.strip():
        return dk.topic.strip()[:120]
    return (item.category or "knowledge")[:120]
