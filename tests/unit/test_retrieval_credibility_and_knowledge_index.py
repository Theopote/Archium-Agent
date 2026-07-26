"""P1: credibility ranker + knowledge vector index."""

from __future__ import annotations

from archium.application.knowledge_fusion import KnowledgeFusionService
from archium.application.knowledge_vector_index import (
    KnowledgeVectorIndexService,
    knowledge_item_embed_text,
)
from archium.application.project_knowledge_service import ProjectKnowledgeService
from archium.application.retrieval_credibility import (
    rank_relevance,
    score_knowledge_credibility,
)
from archium.domain.design_knowledge import DesignKnowledge
from archium.domain.enums import (
    InformationOrigin,
    InformationReliability,
    ProjectType,
)
from archium.domain.knowledge_reference import KnowledgeSourceKind, KnowledgeUsage
from archium.domain.project import Project
from archium.domain.project_knowledge import SourceCitation
from archium.infrastructure.database.repositories import ProjectRepository
from archium.infrastructure.embeddings.mock import MockEmbeddingProvider
from archium.infrastructure.vector.chroma_store import ChromaVectorStore
from sqlalchemy.orm import Session


def test_rank_relevance_penalizes_low_authority_evidence() -> None:
    weak = rank_relevance(
        similarity=0.95,
        authority=0.3,
        transferability=0.9,
        usage=KnowledgeUsage.EVIDENCE,
    )
    strong = rank_relevance(
        similarity=0.7,
        authority=0.92,
        transferability=0.85,
        usage=KnowledgeUsage.EVIDENCE,
        has_citations=True,
    )
    assert strong > weak


def test_rank_relevance_caps_low_transferability() -> None:
    score = rank_relevance(
        similarity=0.95,
        authority=0.9,
        transferability=0.2,
        usage=KnowledgeUsage.ILLUSTRATIVE,
    )
    assert score <= 0.45


def test_knowledge_vector_index_and_fusion(
    db_session: Session,
    test_settings: object,
) -> None:
    project = ProjectRepository(db_session).create(
        Project(name="知识向量", project_type=ProjectType.CULTURE)
    )
    store = ChromaVectorStore(test_settings.chroma_path)  # type: ignore[attr-defined]
    # Force retrieval on for index
    settings = test_settings
    assert settings.retrieval_enabled  # type: ignore[attr-defined]

    service = ProjectKnowledgeService(db_session)
    item = service.create_item(
        project.id,
        statement="山地文化中心宜弱化体量、顺应台地。",
        origin=InformationOrigin.PUBLIC_RESEARCH,
        reliability=InformationReliability.HIGH_CONFIDENCE,
        source_citations=[
            SourceCitation(url="https://example.org/mountain", source_title="山地案例")
        ],
        category="research",
        design_knowledge=DesignKnowledge(
            topic="山地台地",
            insight="弱化体量、顺应地形",
            principle="嵌入而非对峙",
            spatial_translation="退台与院落叠合",
        ),
    )
    # Explicit index with mock embedder (create_item best-effort may no-op if embedder fails)
    index = KnowledgeVectorIndexService(
        db_session,
        settings=settings,  # type: ignore[arg-type]
        embedder=MockEmbeddingProvider(),
        store=store,
    )
    index.index_item(item)
    hits = index.search(project.id, "山地 台地 退台", top_k=3)
    assert hits
    assert hits[0].record_type == "knowledge_item"
    assert hits[0].chunk_id == item.id
    assert hits[0].authority >= 0.7

    text = knowledge_item_embed_text(item)
    assert "退台" in text or "台地" in text

    cred = score_knowledge_credibility(item)
    assert cred.has_citations
    assert cred.transferability >= 0.8

    fusion = KnowledgeFusionService(db_session, settings=settings)  # type: ignore[arg-type]
    # Point fusion's knowledge search at same store via settings path — reindex already done
    refs = fusion.retrieve(project.id, "山地 台地 空间", top_k=8)
    knowledge_refs = [r for r in refs if r.source_kind == KnowledgeSourceKind.KNOWLEDGE_ITEM]
    assert knowledge_refs
    top = knowledge_refs[0]
    assert top.authority >= 0.7
    assert top.relevance > 0.3
