"""P2: knowledge graph + multimodal retrieval."""

from __future__ import annotations

from uuid import uuid4

from archium.application.knowledge_fusion import KnowledgeFusionService
from archium.application.knowledge_graph_service import KnowledgeGraphService
from archium.application.multimodal_retrieval import (
    MultimodalModality,
    MultimodalRetrievalService,
    annotate_from_caption_chunk,
    infer_modality_from_query,
)
from archium.domain.architectural_chunk import ArchitecturalChunkType
from archium.domain.design_knowledge import DesignKnowledge
from archium.domain.document import DocumentChunk, SourceDocument
from archium.domain.enums import (
    DocumentType,
    InformationOrigin,
    InformationReliability,
    ProcessingStatus,
    ProjectType,
)
from archium.domain.knowledge_graph import KnowledgeNodeKind, KnowledgeRelationKind
from archium.domain.knowledge_reference import KnowledgeSourceKind
from archium.domain.project import Project
from archium.domain.project_knowledge import ProjectKnowledgeItem, SourceCitation
from archium.infrastructure.database.repositories import (
    DocumentRepository,
    ProjectKnowledgeRepository,
    ProjectRepository,
)
from sqlalchemy.orm import Session


def test_infer_drawing_and_cad_modality() -> None:
    assert infer_modality_from_query("找总平面图入口") == MultimodalModality.DRAWING
    assert infer_modality_from_query("需要 IFC 模型") == MultimodalModality.BIM


def test_annotate_caption_extracts_spatial_features() -> None:
    chunk = DocumentChunk(
        project_id=uuid4(),
        document_id=uuid4(),
        content="【图纸资产】院落围合，砖木材料，总平面示意入口流线。",
        chunk_index=0,
        content_type="asset_caption",
        metadata={"drawing_type": "site_plan", "asset_id": "a1"},
    )
    ann = annotate_from_caption_chunk(chunk)
    assert ann.modality == MultimodalModality.DRAWING
    assert "院落" in ann.spatial_features or "流线" in ann.spatial_features
    assert "砖" in ann.material_cues or "木" in ann.material_cues


def test_knowledge_graph_builds_case_and_project_nodes(
    db_session: Session,
    test_settings: object,
) -> None:
    project = ProjectRepository(db_session).create(
        Project(name="图谱项目", project_type=ProjectType.CULTURE)
    )
    ProjectKnowledgeRepository(db_session).create(
        ProjectKnowledgeItem(
            project_id=project.id,
            statement="关中院落内向聚合可转译为文化中心庭院。",
            origin=InformationOrigin.PUBLIC_RESEARCH,
            reliability=InformationReliability.HIGH_CONFIDENCE,
            source_citations=[
                SourceCitation(url="https://example.org/c", source_title="院落研究")
            ],
            design_knowledge=DesignKnowledge(
                topic="关中院落",
                insight="内向聚合",
                principle="围合形成公共核",
                spatial_translation="四面围合中心庭院",
                material_strategy="砖木灰瓦",
            ),
            category="research",
        )
    )
    graph = KnowledgeGraphService(db_session, settings=test_settings)  # type: ignore[arg-type]
    snapshot = graph.build_snapshot(project.id)
    kinds = {node.kind for node in snapshot.nodes}
    assert KnowledgeNodeKind.CASE in kinds
    assert KnowledgeNodeKind.KNOWLEDGE_ITEM in kinds
    assert KnowledgeNodeKind.SPACE in kinds or KnowledgeNodeKind.CONCEPT in kinds
    assert any(e.relation == KnowledgeRelationKind.HAS_TAG for e in snapshot.edges)

    refs = graph.retrieve_via_graph(project.id, "院落 庭院 内向", top_k=8)
    assert refs
    assert any(r.source_kind == KnowledgeSourceKind.GRAPH_NODE for r in refs)
    assert any(
        r.extra.get("node_kind") in {"space", "case", "concept", "tag", "knowledge_item"}
        for r in refs
    )


def test_multimodal_retrieval_and_fusion(
    db_session: Session,
    test_settings: object,
) -> None:
    project = ProjectRepository(db_session).create(
        Project(name="多模态项目", project_type=ProjectType.CULTURE)
    )
    repo = DocumentRepository(db_session)
    document = repo.create_document(
        SourceDocument(
            project_id=project.id,
            filename="图纸.pdf",
            original_path="/tmp/图纸.pdf",
            stored_path="/tmp/图纸.pdf",
            file_type=DocumentType.PDF,
            file_hash="d" * 64,
            size_bytes=10,
            processing_status=ProcessingStatus.COMPLETED,
        )
    )
    chunk = DocumentChunk(
        project_id=project.id,
        document_id=document.id,
        content="【图纸资产 · site_plan】院落围合与主入口流线示意。",
        chunk_index=0,
        content_type="asset_caption",
        section_title="总平面",
        metadata={
            "drawing_type": "site_plan",
            "asset_id": str(uuid4()),
            "architectural_type": ArchitecturalChunkType.DRAWING_NOTE.value,
        },
    ).ensure_architectural_annotation()
    repo.create_chunk(chunk)

    mm = MultimodalRetrievalService(db_session, settings=test_settings)  # type: ignore[arg-type]
    mm_refs = mm.retrieve(project.id, "总平面图 院落 入口", top_k=4)
    assert mm_refs
    assert mm_refs[0].source_kind == KnowledgeSourceKind.MULTIMODAL_ASSET

    fusion = KnowledgeFusionService(db_session, settings=test_settings)  # type: ignore[arg-type]
    fused = fusion.retrieve(project.id, "院落 庭院 总平面", top_k=12)
    kinds = {r.source_kind for r in fused}
    assert KnowledgeSourceKind.GRAPH_NODE in kinds or KnowledgeSourceKind.ARCHITECTURE_CASE in kinds
    assert KnowledgeSourceKind.MULTIMODAL_ASSET in kinds
