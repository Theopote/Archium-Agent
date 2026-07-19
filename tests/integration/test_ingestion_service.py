"""Integration tests for document ingestion."""

from __future__ import annotations

from pathlib import Path

import pytest
from archium.application.ingestion_service import IngestionService
from archium.domain.enums import ProcessingStatus, ProjectType
from archium.domain.project import Project
from archium.infrastructure.database.repositories import DocumentRepository, FactRepository, ProjectRepository
from docx import Document
from sqlalchemy.orm import Session

from tests.fixtures.sample_files import create_sample_docx, create_sample_image, create_sample_pdf


@pytest.fixture
def project(db_session: Session) -> Project:
    return ProjectRepository(db_session).create(
        Project(name="某医院老院区更新", project_type=ProjectType.HEALTHCARE)
    )


@pytest.fixture
def ingestion_service(db_session: Session, test_settings: object) -> IngestionService:
    return IngestionService(db_session, settings=test_settings)  # type: ignore[arg-type]


def test_import_pdf_creates_document_and_chunks(
    ingestion_service: IngestionService,
    project: Project,
    tmp_path: Path,
) -> None:
    pdf_path = create_sample_pdf(tmp_path / "项目任务书.pdf")
    result = ingestion_service.import_file(project.id, pdf_path)

    assert result.error is None
    assert result.document is not None
    assert result.document.processing_status in {
        ProcessingStatus.COMPLETED,
        ProcessingStatus.NEEDS_OCR,
    }
    assert result.chunks
    assert result.chunks[0].page_number == 1


def test_import_docx_extracts_metric_facts_at_ingest(
    ingestion_service: IngestionService,
    project: Project,
    tmp_path: Path,
    db_session: Session,
) -> None:
    docx_path = create_sample_docx(
        tmp_path / "规划指标.docx",
        body="规划容积率 2.5，建筑高度 80 米，用地面积约 3.2 公顷。",
    )
    result = ingestion_service.import_file(project.id, docx_path)

    assert result.document is not None
    facts = FactRepository(db_session).list_by_project(project.id)
    keys = {fact.key for fact in facts}
    assert "plot_ratio" in keys
    assert "height" in keys
    assert "site_area" in keys


def test_import_docx_persists_chunks(
    ingestion_service: IngestionService,
    project: Project,
    tmp_path: Path,
    db_session: Session,
) -> None:
    docx_path = create_sample_docx(tmp_path / "现状分析.docx")
    result = ingestion_service.import_file(project.id, docx_path)

    assert result.document is not None
    assert result.document.processing_status == ProcessingStatus.COMPLETED
    repo = DocumentRepository(db_session)
    chunks = repo.list_chunks(result.document.id)
    assert len(chunks) == len(result.chunks)
    assert any("项目背景" in chunk.content for chunk in chunks)


def test_import_image_creates_asset_caption_chunk(
    ingestion_service: IngestionService,
    project: Project,
    tmp_path: Path,
    db_session: Session,
) -> None:
    image_path = create_sample_image(tmp_path / "总图.jpg")
    result = ingestion_service.import_file(project.id, image_path)

    assert result.document is not None
    assert result.assets
    chunks = DocumentRepository(db_session).list_chunks(result.document.id)
    caption_chunks = [chunk for chunk in chunks if chunk.content_type == "asset_caption"]
    assert len(caption_chunks) == 1
    assert "【图纸资产" in caption_chunks[0].content
    assert result.assets[0].description


def test_import_long_pdf_uses_semantic_chunks(
    db_session: Session,
    test_settings: object,
    project: Project,
    tmp_path: Path,
) -> None:
    settings = test_settings.model_copy(update={"chunk_max_chars": 180, "chunk_overlap_chars": 30})  # type: ignore[attr-defined]
    ingestion_service = IngestionService(db_session, settings=settings)  # type: ignore[arg-type]
    docx_path = tmp_path / "长文档.docx"
    document = Document()
    for index in range(1, 21):
        document.add_paragraph(
            f"第{index}段详细描述老院区交通组织、停车系统与流线优化需求。"
        )
    document.save(docx_path)
    result = ingestion_service.import_file(project.id, docx_path)

    assert result.error is None
    assert result.document is not None
    assert len(result.chunks) > 1
    assert all(chunk.metadata.get("chunk_strategy") == "semantic" for chunk in result.chunks)
    assert all(len(chunk.content) <= 180 for chunk in result.chunks)


def test_duplicate_import_is_skipped(
    ingestion_service: IngestionService,
    project: Project,
    tmp_path: Path,
) -> None:
    pdf_path = create_sample_pdf(tmp_path / "duplicate.pdf")
    first = ingestion_service.import_file(project.id, pdf_path)
    second = ingestion_service.import_file(project.id, pdf_path)

    assert first.duplicate is False
    assert second.duplicate is True
    assert second.skipped is True
    assert first.document is not None
    assert second.document is not None
    assert first.document.id == second.document.id


def test_batch_import_continues_after_missing_file(
    ingestion_service: IngestionService,
    project: Project,
    tmp_path: Path,
) -> None:
    valid = create_sample_pdf(tmp_path / "valid.pdf")
    missing = tmp_path / "missing.pdf"
    results = ingestion_service.import_files(project.id, [valid, missing])

    assert len(results) == 2
    assert results[0].error is None
    assert results[1].error is not None
