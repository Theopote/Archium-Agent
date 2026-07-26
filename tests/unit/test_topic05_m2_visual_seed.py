"""Topic 05 Phase M2 — visual IdeaSeed + CAD upload types."""

from __future__ import annotations

from uuid import uuid4

from archium.application.visual_idea_seed import (
    build_visual_seed_raw_input,
    maybe_attach_visual_idea_seed,
)
from archium.domain.architectural_asset import ArchitecturalAssetRole
from archium.domain.asset import Asset
from archium.domain.enums import (
    AssetType,
    ConceptDirectionStatus,
    DocumentPurpose,
    DocumentType,
    ExplorationSessionStatus,
    ProcessingStatus,
    ProjectType,
)
from archium.domain.exploration_session import ExplorationSession
from archium.domain.intent.idea_seed import IdeaSeed
from archium.domain.project import Project
from archium.infrastructure.database.repositories import (
    AssetRepository,
    ConceptDirectionRepository,
    DocumentRepository,
    ExplorationSessionRepository,
    ProjectRepository,
)
from archium.domain.document import SourceDocument
from archium.ui.upload_file_types import PROJECT_MATERIAL_UPLOAD_TYPES
from sqlalchemy.orm import Session


def test_upload_types_include_cad_bim() -> None:
    for suffix in ("dwg", "dxf", "ifc", "rvt", "rfa"):
        assert suffix in PROJECT_MATERIAL_UPLOAD_TYPES
    assert "png" in PROJECT_MATERIAL_UPLOAD_TYPES


def test_build_visual_seed_raw_mentions_photo() -> None:
    asset = Asset(
        project_id=uuid4(),
        filename="site.jpg",
        path="/tmp/site.jpg",
        asset_type=AssetType.PHOTO,
        metadata={"vision_caption": "北侧入口，沿街面低层住宅"},
    )
    text = build_visual_seed_raw_input([(asset, ArchitecturalAssetRole.SITE_PHOTO)])
    assert "现场照片" in text
    assert "北侧入口" in text
    assert "弱种子" in text


def test_attach_creates_weak_session_without_directions(
    db_session: Session,
    test_settings: object,
) -> None:
    project = ProjectRepository(db_session).create(
        Project(name="视觉种子项目", project_type=ProjectType.CULTURE)
    )
    doc = DocumentRepository(db_session).create_document(
        SourceDocument(
            project_id=project.id,
            filename="site.jpg",
            original_path="/tmp/site.jpg",
            stored_path="/tmp/site.jpg",
            file_type=DocumentType.IMAGE,
            file_hash="d" * 64,
            size_bytes=10,
            processing_status=ProcessingStatus.COMPLETED,
            metadata={"purpose": DocumentPurpose.PROJECT_MATERIAL.value},
        )
    )
    asset = AssetRepository(db_session).create(
        Asset(
            project_id=project.id,
            document_id=doc.id,
            filename="site.jpg",
            path="/tmp/site.jpg",
            asset_type=AssetType.PHOTO,
            metadata={"vision_caption": "场地北入口现状"},
        )
    )
    result = maybe_attach_visual_idea_seed(
        db_session,
        project.id,
        assets=[asset],
        document=doc,
        settings=test_settings,  # type: ignore[arg-type]
    )
    assert result.attached
    assert result.created_session
    assert result.exploration_id is not None
    exploration = ExplorationSessionRepository(db_session).get(result.exploration_id)
    assert exploration is not None
    assert exploration.status == ExplorationSessionStatus.EXPLORING
    assert exploration.source == "site_photo"
    assert exploration.idea_seed is not None
    assert exploration.idea_seed.source == "site_photo"
    assert "场地北入口" in exploration.idea_text
    assert not exploration.idea_seed.is_enriched
    directions = ConceptDirectionRepository(db_session).list_by_exploration(
        exploration.id
    )
    assert directions == []


def test_illustrative_asset_does_not_seed(
    db_session: Session,
    test_settings: object,
) -> None:
    project = ProjectRepository(db_session).create(
        Project(name="示意不种子", project_type=ProjectType.CULTURE)
    )
    doc = DocumentRepository(db_session).create_document(
        SourceDocument(
            project_id=project.id,
            filename="gen.png",
            original_path="/tmp/gen.png",
            stored_path="/tmp/gen.png",
            file_type=DocumentType.IMAGE,
            file_hash="e" * 64,
            size_bytes=10,
            processing_status=ProcessingStatus.COMPLETED,
        )
    )
    asset = AssetRepository(db_session).create(
        Asset(
            project_id=project.id,
            document_id=doc.id,
            filename="gen.png",
            path="/tmp/gen.png",
            asset_type=AssetType.PHOTO,
            metadata={"asset_policy": "illustrative_only", "source": "research_vision"},
        )
    )
    result = maybe_attach_visual_idea_seed(
        db_session,
        project.id,
        assets=[asset],
        document=doc,
        settings=test_settings,  # type: ignore[arg-type]
    )
    assert not result.attached
    assert ExplorationSessionRepository(db_session).get_latest_for_project(project.id) is None


def test_merge_into_user_seed_preserves_text(
    db_session: Session,
    test_settings: object,
) -> None:
    project = ProjectRepository(db_session).create(
        Project(name="合并种子", project_type=ProjectType.CULTURE)
    )
    ExplorationSessionRepository(db_session).create(
        ExplorationSession(
            project_id=project.id,
            idea_text="我想做一座滨水文化馆",
            idea_seed=IdeaSeed.from_raw("我想做一座滨水文化馆", source="user"),
            status=ExplorationSessionStatus.EXPLORING,
            source="genesis",
        )
    )
    db_session.commit()
    doc = DocumentRepository(db_session).create_document(
        SourceDocument(
            project_id=project.id,
            filename="plan.png",
            original_path="/tmp/plan.png",
            stored_path="/tmp/plan.png",
            file_type=DocumentType.IMAGE,
            file_hash="f" * 64,
            size_bytes=10,
            processing_status=ProcessingStatus.COMPLETED,
        )
    )
    asset = AssetRepository(db_session).create(
        Asset(
            project_id=project.id,
            document_id=doc.id,
            filename="plan.png",
            path="/tmp/plan.png",
            asset_type=AssetType.DRAWING,
            metadata={"drawing_type": "site_plan", "vision_caption": "沿河总平面"},
        )
    )
    result = maybe_attach_visual_idea_seed(
        db_session,
        project.id,
        assets=[asset],
        document=doc,
        settings=test_settings,  # type: ignore[arg-type]
    )
    assert result.attached
    assert result.merged
    exploration = ExplorationSessionRepository(db_session).get_latest_for_project(
        project.id
    )
    assert exploration is not None
    assert "滨水文化馆" in exploration.idea_text
    assert "补充视觉证据" in exploration.idea_text or "沿河总平面" in exploration.idea_text
    assert exploration.status == ExplorationSessionStatus.EXPLORING
    # Still no selected directions
    dirs = ConceptDirectionRepository(db_session).list_by_exploration(exploration.id)
    assert all(d.status != ConceptDirectionStatus.SELECTED for d in dirs)
