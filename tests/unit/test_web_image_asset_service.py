"""Tests for web image asset persistence."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from archium.application.web_image_asset_service import WebImageAssetService
from archium.config.settings import Settings
from archium.domain.enums import AssetType, ProjectType, VisualType
from archium.domain.fallback_image import FallbackImage
from archium.domain.project import Project
from archium.domain.slide import SlideSpec, VisualRequirement
from archium.infrastructure.database.repositories import AssetRepository, ProjectRepository
from sqlalchemy.orm import Session


@pytest.fixture
def project_id(db_session: Session, tmp_path: Path) -> object:
    settings = Settings(_env_file=None, project_storage_path=tmp_path / "projects")
    project = ProjectRepository(db_session).create(
        Project(name="Web Import Project", project_type=ProjectType.COMMERCIAL)
    )
    (settings.project_storage_path / str(project.id)).mkdir(parents=True, exist_ok=True)
    return project.id


def test_persist_web_image_creates_project_asset(
    db_session: Session,
    tmp_path: Path,
    project_id: object,
) -> None:
    source = tmp_path / "download.jpg"
    source.write_bytes(b"\xff\xd8\xff\xd9")
    slide = SlideSpec(
        id=uuid4(),
        presentation_id=uuid4(),
        chapter_id="ch1",
        order=0,
        title="夜景效果图",
        message="展示灯光",
        visual_requirements=[
            VisualRequirement(
                type=VisualType.RENDERING,
                description="夜景透视",
                required=True,
            )
        ],
    )
    image = FallbackImage(
        path=source,
        generated=True,
        web_sourced=True,
        attribution="Photo by Alex on Pexels",
        source_url="https://www.pexels.com/photo/1/",
        search_query="architecture rendering night",
        provider="pexels",
    )
    settings = Settings(
        _env_file=None,
        project_storage_path=tmp_path / "projects",
        web_image_search_persist_to_library=True,
    )
    service = WebImageAssetService(db_session, settings=settings)
    persisted = service.persist_if_enabled(
        project_id,  # type: ignore[arg-type]
        image,
        slide=slide,
        requirement=slide.visual_requirements[0],
        search_query=image.search_query or "",
    )

    assets = AssetRepository(db_session).list_by_project(project_id)  # type: ignore[arg-type]
    assert len(assets) == 1
    assert assets[0].asset_type == AssetType.IMAGE
    assert assets[0].metadata.get("web_source_url") == image.source_url
    assert persisted.path.exists()
    assert persisted.path.parent.name == "web_imports"


def test_persist_web_image_reuses_existing_source_url(
    db_session: Session,
    tmp_path: Path,
    project_id: object,
) -> None:
    settings = Settings(
        _env_file=None,
        project_storage_path=tmp_path / "projects",
        web_image_search_persist_to_library=True,
    )
    service = WebImageAssetService(db_session, settings=settings)
    slide = SlideSpec(
        id=uuid4(),
        presentation_id=uuid4(),
        chapter_id="ch1",
        order=0,
        title="参考案例",
        message="案例",
        visual_requirements=[
            VisualRequirement(
                type=VisualType.REFERENCE_CASE,
                description="案例外观",
                required=True,
            )
        ],
    )
    source_url = "https://www.pexels.com/photo/duplicate/"
    first_source = tmp_path / "first.jpg"
    first_source.write_bytes(b"\xff\xd8\xff\xd9")
    first = FallbackImage(
        path=first_source,
        web_sourced=True,
        source_url=source_url,
        search_query="case study",
        provider="pexels",
    )
    service.persist_if_enabled(
        project_id,  # type: ignore[arg-type]
        first,
        slide=slide,
        requirement=slide.visual_requirements[0],
        search_query="case study",
    )

    second_source = tmp_path / "second.jpg"
    second_source.write_bytes(b"\xff\xd8\xff\xd8")
    second = FallbackImage(
        path=second_source,
        web_sourced=True,
        source_url=source_url,
        search_query="case study",
        provider="pexels",
    )
    reused = service.persist_if_enabled(
        project_id,  # type: ignore[arg-type]
        second,
        slide=slide,
        requirement=slide.visual_requirements[0],
        search_query="case study",
    )

    assets = AssetRepository(db_session).list_by_project(project_id)  # type: ignore[arg-type]
    assert len(assets) == 1
    assert reused.path.name == assets[0].filename
