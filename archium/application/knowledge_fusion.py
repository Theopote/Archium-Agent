"""Project Knowledge Space fusion — Fact + Chunk + KnowledgeItem (+ optional cases).

Not a new Agent: Service ranks KnowledgeReference with credibility dimensions.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.architecture_case_library import ArchitectureCaseLibraryService
from archium.application.fact_retrieval import match_fact_keys_from_query, rank_facts_for_context
from archium.application.knowledge_isolation import filter_generation_facts, is_reference_document
from archium.application.retrieval_filters import RetrievalFilters
from archium.application.retrieval_hybrid import keyword_overlap_score
from archium.application.retrieval_service import create_retrieval_service
from archium.config.settings import Settings, get_settings
from archium.domain.architectural_chunk import (
    ArchitecturalChunkType,
    architectural_type_from_metadata,
    classify_architectural_chunk,
    infer_types_from_query,
)
from archium.domain.document import DocumentChunk
from archium.domain.enums import InformationReliability, KnowledgeItemStatus, VerificationStatus
from archium.domain.fact import ProjectFact
from archium.domain.knowledge_reference import (
    KnowledgeReference,
    KnowledgeSourceKind,
    KnowledgeUsage,
    fuse_relevance,
)
from archium.domain.project_knowledge import ProjectKnowledgeItem
from archium.infrastructure.database.repositories import (
    DocumentRepository,
    FactRepository,
    ProjectKnowledgeRepository,
)
from archium.infrastructure.vector.chroma_store import VectorSearchHit


_RELIABILITY_AUTHORITY: dict[InformationReliability, float] = {
    InformationReliability.CONFIRMED: 0.95,
    InformationReliability.HIGH_CONFIDENCE: 0.8,
    InformationReliability.UNVERIFIED: 0.4,
    InformationReliability.INFERENCE: 0.35,
    InformationReliability.CONFLICTING: 0.2,
}


class KnowledgeFusionService:
    """Hybrid assemble of project-internal + external-structured knowledge hits."""

    def __init__(
        self,
        session: Session,
        *,
        settings: Settings | None = None,
    ) -> None:
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
    ) -> list[KnowledgeReference]:
        query = (query or "").strip()
        preferred = infer_types_from_query(query)
        refs: list[KnowledgeReference] = []
        refs.extend(self._fact_refs(project_id, query))
        refs.extend(self._chunk_refs(project_id, query, filters=filters, preferred=preferred))
        refs.extend(self._knowledge_item_refs(project_id, query, preferred=preferred))
        if include_cases and query:
            refs.extend(self._case_refs(query))
        refs.sort(key=lambda item: item.relevance, reverse=True)
        return refs[: max(1, top_k)]

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
            authority = 0.92 if fact.is_confirmed else min(0.75, 0.4 + float(fact.confidence) * 0.4)
            transferability = 1.0  # project-local facts always apply
            refs.append(
                KnowledgeReference(
                    source_kind=KnowledgeSourceKind.FACT,
                    source_id=str(fact.id),
                    content=self._format_fact(fact),
                    title=fact.label,
                    similarity=similarity,
                    authority=authority,
                    transferability=transferability,
                    relevance=fuse_relevance(
                        similarity=similarity,
                        authority=authority,
                        transferability=transferability,
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

        hit_scores = {hit.chunk_id: hit.score for hit in hits}
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
            similarity = hit_scores.get(chunk.id)
            if similarity is None:
                similarity = keyword_overlap_score(query, chunk.content) if query else 0.3
            if preferred and arch in preferred:
                similarity = min(1.0, float(similarity) + 0.12)
            authority = 0.7 if chunk.content_type != "asset_caption" else 0.55
            transferability = 0.75 if arch != ArchitecturalChunkType.GENERAL else 0.55
            if preferred and arch in preferred:
                transferability = min(1.0, transferability + 0.15)
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
                    authority=authority,
                    transferability=transferability,
                    relevance=fuse_relevance(
                        similarity=float(similarity),
                        authority=authority,
                        transferability=transferability,
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
        refs: list[KnowledgeReference] = []
        for item in items:
            text = item.statement
            dk = item.design_knowledge
            if dk is not None and dk.has_substance:
                text = "\n".join(
                    part
                    for part in (
                        dk.insight,
                        dk.principle,
                        dk.spatial_translation,
                        dk.material_strategy,
                        item.statement,
                    )
                    if part and str(part).strip()
                )
            similarity = keyword_overlap_score(query, text) if query else 0.35
            if similarity < 0.15 and query:
                continue
            authority = _RELIABILITY_AUTHORITY.get(item.reliability, 0.4)
            transferability = 0.85 if dk is not None and dk.has_substance else 0.55
            if preferred and dk is not None:
                if any(
                    t in preferred
                    for t in (
                        ArchitecturalChunkType.SPATIAL_STRATEGY,
                        ArchitecturalChunkType.DESIGN_CONCEPT,
                        ArchitecturalChunkType.MATERIAL_STRATEGY,
                    )
                ):
                    transferability = min(1.0, transferability + 0.1)
            usage = (
                KnowledgeUsage.DESIGN_JUDGMENT
                if dk is not None and dk.has_substance
                else KnowledgeUsage.BACKGROUND
            )
            arch = None
            if dk is not None:
                if dk.spatial_translation.strip():
                    arch = ArchitecturalChunkType.SPATIAL_STRATEGY
                elif dk.material_strategy.strip():
                    arch = ArchitecturalChunkType.MATERIAL_STRATEGY
                elif dk.principle.strip() or dk.insight.strip():
                    arch = ArchitecturalChunkType.DESIGN_CONCEPT
            refs.append(
                KnowledgeReference(
                    source_kind=KnowledgeSourceKind.KNOWLEDGE_ITEM,
                    source_id=str(item.id),
                    content=text[:1500],
                    title=(dk.topic if dk and dk.topic.strip() else item.category)[:120],
                    similarity=max(0.2, similarity),
                    authority=authority,
                    transferability=transferability,
                    relevance=fuse_relevance(
                        similarity=max(0.2, similarity),
                        authority=authority,
                        transferability=transferability,
                    ),
                    usage=usage,
                    architectural_type=arch,
                    project_id=project_id,
                    extra={"origin": item.origin.value, "reliability": item.reliability.value},
                )
            )
        return refs

    def _case_refs(self, query: str) -> list[KnowledgeReference]:
        library = ArchitectureCaseLibraryService()
        cases = library.search(query, limit=2)
        refs: list[KnowledgeReference] = []
        for match in cases:
            case = match.case
            text = case.to_prompt_block()
            similarity = max(float(match.score), keyword_overlap_score(query, text))
            authority = 0.8
            transferability = 0.7 if case.transferable_principles else 0.5
            refs.append(
                KnowledgeReference(
                    source_kind=KnowledgeSourceKind.ARCHITECTURE_CASE,
                    source_id=case.id,
                    content=text[:1500],
                    title=case.name,
                    similarity=max(0.25, similarity),
                    authority=authority,
                    transferability=transferability,
                    relevance=fuse_relevance(
                        similarity=max(0.25, similarity),
                        authority=authority,
                        transferability=transferability,
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
