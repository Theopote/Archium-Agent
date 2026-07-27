"""Topic 05 — ArchitecturalAsset facade, evidence usage, OCR helpers."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from archium.application.ingestion_service import IngestionService
from archium.application.multimodal_retrieval import MultimodalRetrievalService
from archium.application.visual_evidence_service import build_visual_evidence_pack
from archium.domain.architectural_asset import (
    ArchitecturalAssetRole,
    architectural_asset_from_parts,
    infer_architectural_asset_role,
    infer_architectural_asset_usage,
    input_source_lines_from_assets,
)
from archium.domain.asset import Asset
from archium.domain.document import DocumentChunk, SourceDocument
from archium.domain.enums import (
    AssetType,
    DocumentPurpose,
    DocumentType,
    ProcessingStatus,
    ProjectType,
)
from archium.domain.knowledge_reference import KnowledgeUsage
from archium.domain.project import Project
from archium.infrastructure.database.repositories import (
    AssetRepository,
    DocumentRepository,
    ProjectRepository,
)
from archium.infrastructure.vision.ocr_text import is_meaningful_ocr_text
from sqlalchemy.orm import Session


def test_infer_site_photo_and_drawing_roles() -> None:
    photo = Asset(
        project_id=uuid4(),
        filename="site.jpg",
        path="/tmp/site.jpg",
        asset_type=AssetType.PHOTO,
    )
    drawing = Asset(
        project_id=uuid4(),
        filename="plan.png",
        path="/tmp/plan.png",
        asset_type=AssetType.IMAGE,
        metadata={"drawing_type": "site_plan"},
    )
    assert infer_architectural_asset_role(photo) == ArchitecturalAssetRole.SITE_PHOTO
    assert infer_architectural_asset_role(drawing) == ArchitecturalAssetRole.DRAWING
    assert (
        infer_architectural_asset_usage(ArchitecturalAssetRole.SITE_PHOTO)
        == KnowledgeUsage.EVIDENCE
    )
    assert (
        infer_architectural_asset_usage(
            ArchitecturalAssetRole.REFERENCE,
            document_purpose=DocumentPurpose.REFERENCE_STYLE,
        )
        == KnowledgeUsage.ILLUSTRATIVE
    )


def test_generated_asset_stays_illustrative() -> None:
    asset = Asset(
        project_id=uuid4(),
        filename="gen.png",
        path="/tmp/gen.png",
        asset_type=AssetType.PHOTO,
        metadata={"asset_policy": "illustrative_only", "source": "research_vision"},
    )
    facade = architectural_asset_from_parts(asset)
    assert facade.role == ArchitecturalAssetRole.REFERENCE
    assert facade.usage == KnowledgeUsage.ILLUSTRATIVE


def test_input_source_lines_from_roles() -> None:
    pid = uuid4()
    assets = [
        architectural_asset_from_parts(
            Asset(
                project_id=pid,
                filename="a.jpg",
                path="/a",
                asset_type=AssetType.PHOTO,
            )
        ),
        architectural_asset_from_parts(
            Asset(
                project_id=pid,
                filename="b.png",
                path="/b",
                asset_type=AssetType.DRAWING,
                metadata={"drawing_type": "floor_plan"},
            )
        ),
    ]
    lines = input_source_lines_from_assets(assets)
    assert "site_photo:1" in lines
    assert "drawing:1" in lines


def test_meaningful_ocr_threshold() -> None:
    assert not is_meaningful_ocr_text("hi")
    assert is_meaningful_ocr_text("场地现状：入口在北侧，沿街面约 40 米。")


def test_visual_evidence_pack_and_context_sources(
    db_session: Session,
    test_settings: object,
) -> None:
    project = ProjectRepository(db_session).create(
        Project(name="视觉证据项目", project_type=ProjectType.CULTURE)
    )
    doc = DocumentRepository(db_session).create_document(
        SourceDocument(
            project_id=project.id,
            filename="现场.pdf",
            original_path="/tmp/现场.pdf",
            stored_path="/tmp/现场.pdf",
            file_type=DocumentType.PDF,
            file_hash="a" * 64,
            size_bytes=10,
            processing_status=ProcessingStatus.COMPLETED,
            metadata={"purpose": DocumentPurpose.PROJECT_MATERIAL.value},
        )
    )
    AssetRepository(db_session).create(
        Asset(
            project_id=project.id,
            document_id=doc.id,
            filename="site.jpg",
            path="/tmp/site.jpg",
            asset_type=AssetType.PHOTO,
        )
    )
    AssetRepository(db_session).create(
        Asset(
            project_id=project.id,
            document_id=doc.id,
            filename="plan.png",
            path="/tmp/plan.png",
            asset_type=AssetType.DRAWING,
            metadata={"drawing_type": "site_plan"},
        )
    )
    pack = build_visual_evidence_pack(db_session, project.id)
    assert pack.site_photo_count == 1
    assert pack.drawing_count == 1
    lines = pack.input_source_lines()
    assert "site_photo:1" in lines
    assert "drawing:1" in lines

    from archium.application.context.project_context_composer import compose_project_context
    from archium.application.context.types import ContextAssessment
    from archium.application.context_evidence import gather_project_evidence
    from archium.domain.intent.knowledge_state import KnowledgeState

    evidence = gather_project_evidence(db_session, project.id)
    assert evidence.site_photo_count == 1
    assert "site_photo:1" in evidence.visual_input_sources
    assessment = ContextAssessment(
        knowledge_state=KnowledgeState(),
        actions=[],
    )
    ctx = compose_project_context(assessment, evidence=evidence)
    assert any(s.startswith("site_photo:") for s in ctx.input_sources)
    assert any(s.startswith("drawing:") for s in ctx.input_sources)


def test_multimodal_retrieval_uses_evidence_for_project_drawing(
    db_session: Session,
    test_settings: object,
) -> None:
    project = ProjectRepository(db_session).create(
        Project(name="证据检索项目", project_type=ProjectType.CULTURE)
    )
    repo = DocumentRepository(db_session)
    document = repo.create_document(
        SourceDocument(
            project_id=project.id,
            filename="图纸.pdf",
            original_path="/tmp/图纸.pdf",
            stored_path="/tmp/图纸.pdf",
            file_type=DocumentType.PDF,
            file_hash="b" * 64,
            size_bytes=10,
            processing_status=ProcessingStatus.COMPLETED,
            metadata={"purpose": DocumentPurpose.PROJECT_MATERIAL.value},
        )
    )
    chunk = DocumentChunk(
        project_id=project.id,
        document_id=document.id,
        content="【图纸资产 · site_plan】院落围合与主入口流线示意。",
        chunk_index=0,
        content_type="asset_caption",
        metadata={"drawing_type": "site_plan", "asset_id": str(uuid4())},
    ).ensure_architectural_annotation()
    repo.create_chunk(chunk)

    mm = MultimodalRetrievalService(db_session, settings=test_settings)  # type: ignore[arg-type]
    refs = mm.retrieve(project.id, "总平面图 院落", top_k=4)
    assert refs
    assert refs[0].usage == KnowledgeUsage.EVIDENCE


def test_ocr_chunks_when_needs_ocr(
    db_session: Session,
    test_settings: object,
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    from PIL import Image

    project = ProjectRepository(db_session).create(
        Project(name="OCR项目", project_type=ProjectType.CULTURE)
    )
    img_path = tmp_path / "scan.png"
    Image.new("RGB", (640, 480), color=(240, 240, 240)).save(img_path)

    monkeypatch.setattr(
        "archium.infrastructure.vision.ocr_text.extract_text_from_image",
        lambda path, **kwargs: "场地入口在北侧，沿街面约四十米，现状为低层住宅。",
    )
    monkeypatch.setattr(
        "archium.infrastructure.vision.ocr_text.pytesseract_available",
        lambda: True,
    )

    # Drive OCR path via IngestionService helper with a fake document+asset
    service = IngestionService(db_session, settings=test_settings)  # type: ignore[arg-type]
    document = DocumentRepository(db_session).create_document(
        SourceDocument(
            project_id=project.id,
            filename="scan.pdf",
            original_path=str(img_path),
            stored_path=str(img_path),
            file_type=DocumentType.PDF,
            file_hash="c" * 64,
            size_bytes=10,
            processing_status=ProcessingStatus.PROCESSING,
        )
    )
    asset = AssetRepository(db_session).create(
        Asset(
            project_id=project.id,
            document_id=document.id,
            filename="scan.png",
            path=str(img_path),
            asset_type=AssetType.IMAGE,
            page_number=1,
        )
    )
    chunks, ok = service._maybe_ocr_document_assets(
        project.id,
        document,
        [asset],
        needs_ocr=True,
        base_chunk_index=0,
    )
    assert ok
    assert chunks
    assert chunks[0].content_type == "ocr_text"
    assert "入口" in chunks[0].content
