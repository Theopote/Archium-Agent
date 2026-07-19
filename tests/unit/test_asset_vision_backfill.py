"""Tests for asset vision backfill."""

from __future__ import annotations

from pathlib import Path

import pytest
from archium.application.asset_vision_rag_service import AssetVisionBackfillService
from archium.config.settings import Settings
from archium.domain.asset import Asset
from archium.domain.document import SourceDocument
from archium.domain.enums import AssetType, DocumentType, ProcessingStatus
from archium.domain.project import Project
from archium.infrastructure.database.repositories import (
    AssetRepository,
    DocumentRepository,
    ProjectRepository,
)
from sqlalchemy.orm import Session

from tests.fixtures.sample_files import create_sample_image


@pytest.fixture
def project(db_session: Session) -> Project:
    return ProjectRepository(db_session).create(Project(name="回填项目"))


def test_backfill_creates_missing_asset_caption_chunks(
    db_session: Session,
    project: Project,
    tmp_path: Path,
) -> None:
    document = DocumentRepository(db_session).create_document(
        SourceDocument(
            project_id=project.id,
            filename="旧图纸.pdf",
            original_path="/tmp/old.pdf",
            stored_path="/tmp/old.pdf",
            file_type=DocumentType.PDF,
            file_hash="c" * 64,
            size_bytes=1024,
            processing_status=ProcessingStatus.COMPLETED,
        )
    )
    image_path = create_sample_image(tmp_path / "embedded.jpg")
    AssetRepository(db_session).create(
        Asset(
            project_id=project.id,
            document_id=document.id,
            filename=image_path.name,
            path=str(image_path),
            asset_type=AssetType.IMAGE,
            width=800,
            height=600,
            page_number=1,
        )
    )

    result = AssetVisionBackfillService(
        db_session,
        settings=Settings(_env_file=None, asset_vision_rag_enabled=True),
    ).backfill_project(project.id)

    assert result.assets_processed == 1
    assert result.chunks_created == 1
    chunks = DocumentRepository(db_session).list_chunks(document.id)
    assert any(chunk.content_type == "asset_caption" for chunk in chunks)

    second = AssetVisionBackfillService(
        db_session,
        settings=Settings(_env_file=None, asset_vision_rag_enabled=True),
    ).backfill_project(project.id)
    assert second.chunks_created == 0
