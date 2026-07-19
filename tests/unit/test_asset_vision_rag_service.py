"""Unit tests for asset vision caption + RAG chunk generation."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from archium.application.asset_vision_rag_service import (
    AssetVisionRagService,
    build_asset_caption_chunk_text,
)
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
from archium.infrastructure.llm import LLMRequest, MockLLMProvider
from archium.infrastructure.llm.asset_schemas import AssetVisionCaptionDraft
from sqlalchemy.orm import Session

from tests.fixtures.sample_files import create_sample_image

ASSET_VISION_JSON = """{
  "drawing_type": "site_plan",
  "summary": "总平面图展示院区主入口、门诊楼与住院楼布局，东侧保留绿化缓冲带。",
  "spatial_elements": ["主入口广场", "门诊楼", "住院楼"],
  "annotations": ["退线标注", "消防环路"],
  "metrics_visible": ["容积率 2.5"],
  "scale_or_north": "1:500，指北针朝上"
}"""


def _vision_selector(request: LLMRequest) -> str | None:
    if "建筑项目图档" in request.user_prompt:
        return ASSET_VISION_JSON
    return None


@pytest.fixture
def project(db_session: Session) -> Project:
    return ProjectRepository(db_session).create(Project(name="Vision RAG 项目"))


@pytest.fixture
def document(db_session: Session, project: Project) -> SourceDocument:
    return DocumentRepository(db_session).create_document(
        SourceDocument(
            project_id=project.id,
            filename="图纸集.pdf",
            original_path="/tmp/plans.pdf",
            stored_path="/tmp/plans.pdf",
            file_type=DocumentType.PDF,
            file_hash="a" * 64,
            size_bytes=1024,
            processing_status=ProcessingStatus.COMPLETED,
        )
    )


def test_build_asset_caption_chunk_text_includes_structured_fields() -> None:
    asset = Asset(
        project_id=uuid4(),
        filename="site_plan.png",
        path="/tmp/site_plan.png",
        asset_type=AssetType.IMAGE,
        width=1600,
        height=1200,
        page_number=3,
    )
    caption = AssetVisionCaptionDraft(
        drawing_type="site_plan",
        summary="总平面图。",
        spatial_elements=["门诊楼"],
        metrics_visible=["容积率 2.5"],
    )
    text = build_asset_caption_chunk_text(asset, caption, document_name="任务书.pdf")
    assert "【图纸资产 · site_plan】" in text
    assert "可见指标：容积率 2.5" in text
    assert "p.3" in text


def test_process_document_assets_heuristic_creates_chunk(
    db_session: Session,
    project: Project,
    document: SourceDocument,
    tmp_path: Path,
) -> None:
    image_path = create_sample_image(tmp_path / "plan.jpg")
    asset = AssetRepository(db_session).create(
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
    service = AssetVisionRagService(
        db_session,
        settings=Settings(_env_file=None, asset_vision_rag_enabled=True),
    )
    result = service.process_document_assets(
        project.id,
        document,
        [asset],
        base_chunk_index=2,
    )

    assert len(result.chunks) == 1
    chunk = result.chunks[0]
    assert chunk.content_type == "asset_caption"
    assert chunk.chunk_index == 2
    assert "【图纸资产" in chunk.content
    assert result.assets[0].description
    assert result.assets[0].metadata.get("vision_caption")


def test_process_document_assets_llm_caption(
    db_session: Session,
    project: Project,
    document: SourceDocument,
    tmp_path: Path,
) -> None:
    image_path = create_sample_image(tmp_path / "plan_llm.jpg")
    asset = AssetRepository(db_session).create(
        Asset(
            project_id=project.id,
            document_id=document.id,
            filename=image_path.name,
            path=str(image_path),
            asset_type=AssetType.DRAWING,
            width=800,
            height=600,
        )
    )
    mock_llm = MockLLMProvider(selector=_vision_selector)
    service = AssetVisionRagService(
        db_session,
        llm=mock_llm,
        settings=Settings(
            _env_file=None,
            asset_vision_rag_enabled=True,
            asset_vision_llm_enabled=True,
            llm_api_key="test",
        ),
    )
    result = service.process_document_assets(
        project.id,
        document,
        [asset],
        base_chunk_index=0,
    )

    assert len(result.chunks) == 1
    assert "总平面图" in result.chunks[0].content
    assert result.assets[0].metadata.get("vision_source") == "llm_vision"
    assert len(mock_llm.calls) == 1
