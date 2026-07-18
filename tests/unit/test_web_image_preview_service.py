"""Tests for web image preview and adopt flow."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from archium.application.web_image_preview_service import WebImagePreviewService
from archium.config.settings import Settings
from archium.domain.enums import AssetType, ProjectType, VisualType
from archium.domain.presentation import Presentation
from archium.domain.project import Project
from archium.domain.slide import SlideSpec, VisualRequirement
from archium.infrastructure.database.repositories import AssetRepository, PresentationRepository, ProjectRepository
from archium.infrastructure.images.web_search.models import WebImageCandidate
from archium.infrastructure.images.web_search.service import WebImageSearchService
from sqlalchemy.orm import Session


def test_preview_returns_candidates_without_download(db_session: Session) -> None:
    slide = SlideSpec(
        id=uuid4(),
        presentation_id=uuid4(),
        chapter_id="ch1",
        order=0,
        title="夜景效果图",
        message="灯光",
        visual_requirements=[
            VisualRequirement(
                type=VisualType.RENDERING,
                description="夜景透视",
                required=True,
            )
        ],
    )

    class FakeProvider:
        provider_name = "pexels"

        def search(self, query: str, *, per_page: int = 5):
            return [
                WebImageCandidate(
                    download_url="https://images.pexels.com/photos/1.jpeg",
                    page_url="https://www.pexels.com/photo/1/",
                    attribution="Photo by Alex on Pexels",
                )
            ]

    settings = Settings(_env_file=None, web_image_search_enabled=True, pexels_api_key="key")
    service = WebImagePreviewService(
        db_session,
        settings=settings,
        web_search=WebImageSearchService(settings, providers=[FakeProvider()]),  # type: ignore[list-item]
    )
    result = service.preview_requirement(slide, slide.visual_requirements[0])
    assert result is not None
    assert "architecture rendering" in result.query
    assert len(result.items) == 1
    assert result.items[0].provider == "pexels"


def test_adopt_candidate_assigns_asset_to_slide(
    db_session: Session,
    tmp_path: Path,
) -> None:
    project_id = ProjectRepository(db_session).create(
        Project(name="Preview Project", project_type=ProjectType.COMMERCIAL)
    ).id
    presentation_id = PresentationRepository(db_session).create_presentation(
        Presentation(project_id=project_id, title="Preview")  # type: ignore[arg-type]
    ).id
    slide = PresentationRepository(db_session).save_slide(
        SlideSpec(
            presentation_id=presentation_id,
            chapter_id="ch1",
            order=0,
            title="现场照片",
            message="入口",
            visual_requirements=[
                VisualRequirement(
                    type=VisualType.SITE_PHOTO,
                    description="主入口",
                    required=True,
                )
            ],
        )
    )

    settings = Settings(
        _env_file=None,
        web_image_search_enabled=True,
        web_image_search_persist_to_library=True,
        project_storage_path=tmp_path / "projects",
        pexels_api_key="key",
    )

    from archium.infrastructure.images.web_search import downloader as download_module

    original_download = download_module.download_image

    def fake_download(url: str, dest: Path, **kwargs):
        kwargs.pop("fetch_bytes", None)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"\xff\xd8\xff\xd9")
        return dest

    download_module.download_image = fake_download  # type: ignore[assignment]
    try:
        class FakeProvider:
            provider_name = "pexels"

            def search(self, query: str, *, per_page: int = 5):
                return [
                    WebImageCandidate(
                        download_url="https://images.pexels.com/photos/1.jpeg",
                        page_url="https://www.pexels.com/photo/1/",
                        attribution="Photo by Alex on Pexels",
                    )
                ]

        service = WebImagePreviewService(
            db_session,
            settings=settings,
            web_search=WebImageSearchService(settings, providers=[FakeProvider()]),  # type: ignore[list-item]
        )
        preview = service.preview_requirement(slide, slide.visual_requirements[0])
        assert preview is not None
        asset = service.adopt_candidate(
            project_id,  # type: ignore[arg-type]
            slide.id,
            0,
            item=preview.items[0],
            search_query=preview.query,
            confirm=True,
        )
    finally:
        download_module.download_image = original_download

    updated = PresentationRepository(db_session).get_slide(slide.id)
    assert updated is not None
    assert updated.visual_requirements[0].preferred_asset_ids == [asset.id]
    assert updated.visual_requirements[0].confirmed is True
    assets = AssetRepository(db_session).list_by_project(project_id)  # type: ignore[arg-type]
    assert len(assets) == 1
    assert assets[0].asset_type == AssetType.PHOTO
    assert "web_import" in assets[0].tags
