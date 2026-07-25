"""Unit tests for architectural chunk typing and knowledge fusion."""

from __future__ import annotations

from sqlalchemy.orm import Session

from archium.application.knowledge_fusion import KnowledgeFusionService
from archium.application.retrieval_filters import RetrievalFilters
from archium.application.retrieval_service import RetrievalService
from archium.domain.architectural_chunk import (
    ArchitecturalChunkType,
    classify_architectural_chunk,
    infer_types_from_query,
)
from archium.domain.design_knowledge import DesignKnowledge
from archium.domain.document import DocumentChunk, SourceDocument
from archium.domain.enums import (
    DocumentType,
    InformationOrigin,
    InformationReliability,
    ProcessingStatus,
    ProjectType,
    VerificationStatus,
)
from archium.domain.fact import ProjectFact
from archium.domain.knowledge_reference import KnowledgeSourceKind, fuse_relevance
from archium.domain.project import Project
from archium.domain.project_knowledge import ProjectKnowledgeItem
from archium.infrastructure.database.repositories import (
    DocumentRepository,
    FactRepository,
    ProjectKnowledgeRepository,
    ProjectRepository,
)
from archium.infrastructure.embeddings.mock import MockEmbeddingProvider
from archium.infrastructure.vector.chroma_store import ChromaVectorStore


def test_classify_spatial_and_drawing() -> None:
    spatial = classify_architectural_chunk(
        "关中传统院落强调内向聚合，四面围合形成中心庭院。",
        section_title="空间组织",
    )
    assert spatial.chunk_type == ArchitecturalChunkType.SPATIAL_STRATEGY
    assert spatial.design_topics

    drawing = classify_architectural_chunk(
        "总平面图展示主入口",
        content_type="asset_caption",
    )
    assert drawing.chunk_type == ArchitecturalChunkType.DRAWING_NOTE


def test_infer_types_from_query() -> None:
    types = infer_types_from_query("适合北方寒冷地区的院落空间策略")
    assert ArchitecturalChunkType.SPATIAL_STRATEGY in types


def test_fuse_relevance_weights_authority() -> None:
    low = fuse_relevance(similarity=0.9, authority=0.2, transferability=0.2)
    high = fuse_relevance(similarity=0.6, authority=0.95, transferability=0.9)
    assert high > low


def test_retrieval_filter_architectural_type(
    db_session: Session,
    test_settings: object,
) -> None:
    project = ProjectRepository(db_session).create(
        Project(name="建筑类型过滤", project_type=ProjectType.HEALTHCARE)
    )
    repo = DocumentRepository(db_session)
    document = repo.create_document(
        SourceDocument(
            project_id=project.id,
            filename="案例.pdf",
            original_path="/tmp/案例.pdf",
            stored_path="/tmp/案例.pdf",
            file_type=DocumentType.PDF,
            file_hash="c" * 64,
            size_bytes=100,
            processing_status=ProcessingStatus.COMPLETED,
        )
    )
    spatial = DocumentChunk(
        project_id=project.id,
        document_id=document.id,
        content="空间策略：内向院落围合，路径转折进入。",
        section_title="空间组织",
        chunk_index=0,
    ).ensure_architectural_annotation()
    material = DocumentChunk(
        project_id=project.id,
        document_id=document.id,
        content="材料策略：采用砖木与灰瓦屋面表达地域性。",
        section_title="材料",
        chunk_index=1,
    ).ensure_architectural_annotation()
    saved = [repo.create_chunk(spatial), repo.create_chunk(material)]
    assert saved[0].architectural_type == ArchitecturalChunkType.SPATIAL_STRATEGY

    store = ChromaVectorStore(test_settings.chroma_path)  # type: ignore[attr-defined]
    service = RetrievalService(
        db_session,
        settings=test_settings,  # type: ignore[arg-type]
        embedder=MockEmbeddingProvider(),
        store=store,
    )
    service.index_chunks(project.id, saved, document_name="案例.pdf")
    filtered = service.retrieve(
        project.id,
        "院落 空间",
        top_k=5,
        filters=RetrievalFilters(
            architectural_types=(ArchitecturalChunkType.SPATIAL_STRATEGY,),
        ),
    )
    assert filtered
    assert all(
        c.architectural_type == ArchitecturalChunkType.SPATIAL_STRATEGY for c in filtered
    )


def test_knowledge_fusion_ranks_structured_sources(
    db_session: Session,
    test_settings: object,
) -> None:
    project = ProjectRepository(db_session).create(
        Project(name="知识融合", project_type=ProjectType.HEALTHCARE)
    )
    FactRepository(db_session).create(
        ProjectFact(
            project_id=project.id,
            key="site_area",
            label="用地面积",
            value=12000,
            unit="㎡",
            verification_status=VerificationStatus.USER_CONFIRMED,
            confidence=0.95,
        )
    )
    ProjectKnowledgeRepository(db_session).create(
        ProjectKnowledgeItem(
            project_id=project.id,
            statement="山地文化中心宜弱化体量、顺应台地。",
            origin=InformationOrigin.PUBLIC_RESEARCH,
            reliability=InformationReliability.HIGH_CONFIDENCE,
            design_knowledge=DesignKnowledge(
                topic="山地台地",
                insight="弱化体量、顺应地形",
                principle="嵌入而非对峙",
                spatial_translation="退台与院落叠合",
            ),
            category="research",
        )
    )
    fusion = KnowledgeFusionService(db_session, settings=test_settings)  # type: ignore[arg-type]
    refs = fusion.retrieve(project.id, "山地 台地 空间 用地面积", top_k=10)
    kinds = {ref.source_kind for ref in refs}
    assert KnowledgeSourceKind.FACT in kinds
    assert KnowledgeSourceKind.KNOWLEDGE_ITEM in kinds
    assert refs[0].relevance >= refs[-1].relevance
    block = fusion.format_prompt_block(refs)
    assert "KnowledgeReference" in block
    assert "auth=" in block
