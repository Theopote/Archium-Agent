"""Unit tests for visual fallback resolution."""

from __future__ import annotations

from pathlib import Path

import pytest
from archium.application.visual_fallback_service import VisualFallbackService
from archium.config.settings import Settings
from archium.domain.asset import Asset
from archium.domain.enums import AssetType, ProjectType, VisualType
from archium.domain.fallback_image import FallbackImage
from archium.domain.presentation import Presentation
from archium.domain.project import Project
from archium.domain.slide import SlideSpec, VisualRequirement
from archium.domain.visual_qa import VisualQAReport
from archium.infrastructure.database.repositories import (
    AssetRepository,
    PresentationRepository,
    ProjectRepository,
    VisualQAReportRepository,
)
from sqlalchemy.orm import Session


@pytest.fixture
def project_id(db_session: Session) -> object:
    return ProjectRepository(db_session).create(
        Project(name="Fallback Project", project_type=ProjectType.HEALTHCARE)
    ).id


def test_relaxed_matching_uses_drawing_classifier(
    tmp_path: Path,
    db_session: Session,
    project_id: object,
) -> None:
    pytest.importorskip("PIL")
    asset_repo = AssetRepository(db_session)
    site_asset = asset_repo.create(
        Asset(
            project_id=project_id,  # type: ignore[arg-type]
            filename="IMG_001.jpg",
            path=str(tmp_path / "site.jpg"),
            asset_type=AssetType.IMAGE,
        )
    )
    (tmp_path / "site.jpg").write_bytes(b"fake")

    VisualQAReportRepository(db_session).save(
        VisualQAReport(
            asset_id=site_asset.id,
            asset_path=str(tmp_path / "site.jpg"),
            width=1200,
            height=900,
            drawing_type="site_plan",
            drawing_type_confidence=0.9,
        ),
        file_hash="a" * 64,
        analyzer_version="1.0.0",
    )

    pres = PresentationRepository(db_session).create_presentation(
        Presentation(project_id=project_id, title="Test")  # type: ignore[arg-type]
    )
    slide = PresentationRepository(db_session).save_slide(
        SlideSpec(
            presentation_id=pres.id,
            chapter_id="ch1",
            order=0,
            title="总图",
            message="交通组织",
            visual_requirements=[
                VisualRequirement(
                    type=VisualType.SITE_PLAN,
                    description="总平面图",
                    required=True,
                )
            ],
        )
    )

    settings = Settings(
        _env_file=None,
        visual_fallback_enabled=True,
        visual_fallback_relaxed_matching=True,
        visual_fallback_relaxed_min_score=0.2,
        visual_fallback_generate_diagrams=False,
        project_storage_path=tmp_path,
    )
    resolved = VisualFallbackService(db_session, settings=settings).resolve_export_images(
        project_id,  # type: ignore[arg-type]
        [slide],
        output_dir=tmp_path / "out",
        base_paths={},
    )
    assert resolved[(slide.id, 0)].path == Path(site_asset.path)


def test_generates_diagram_when_no_asset_available(
    tmp_path: Path,
    db_session: Session,
    project_id: object,
) -> None:
    pytest.importorskip("PIL")
    pres = PresentationRepository(db_session).create_presentation(
        Presentation(project_id=project_id, title="Test")  # type: ignore[arg-type]
    )
    slide = PresentationRepository(db_session).save_slide(
        SlideSpec(
            presentation_id=pres.id,
            chapter_id="ch1",
            order=0,
            title="流线示意",
            message="人车分流",
            key_points=["主入口", "环路", "后勤通道"],
            visual_requirements=[
                VisualRequirement(
                    type=VisualType.DIAGRAM,
                    description="交通流线示意",
                    required=True,
                )
            ],
        )
    )

    settings = Settings(
        _env_file=None,
        visual_fallback_enabled=True,
        visual_fallback_relaxed_matching=False,
        visual_fallback_generate_diagrams=True,
        project_storage_path=tmp_path,
    )
    output_dir = tmp_path / "presentation" / "out"
    resolved = VisualFallbackService(db_session, settings=settings).resolve_export_images(
        project_id,  # type: ignore[arg-type]
        [slide],
        output_dir=output_dir,
        base_paths={},
    )
    generated = resolved[(slide.id, 0)].path
    assert generated.exists()
    assert generated.suffix == ".png"


def test_web_search_used_for_rendering_before_diagram(
    tmp_path: Path,
    db_session: Session,
    project_id: object,
) -> None:
    pres = PresentationRepository(db_session).create_presentation(
        Presentation(project_id=project_id, title="Test")  # type: ignore[arg-type]
    )
    slide = PresentationRepository(db_session).save_slide(
        SlideSpec(
            presentation_id=pres.id,
            chapter_id="ch1",
            order=0,
            title="主入口效果图",
            message="夜景透视",
            visual_requirements=[
                VisualRequirement(
                    type=VisualType.RENDERING,
                    description="主入口透视",
                    required=True,
                )
            ],
        )
    )

    web_file = tmp_path / "presentation" / "generated" / f"web_{slide.id}_0.jpg"
    web_file.parent.mkdir(parents=True, exist_ok=True)
    web_file.write_bytes(b"\xff\xd8\xff\xd9")

    settings = Settings(
        _env_file=None,
        visual_fallback_enabled=True,
        visual_fallback_relaxed_matching=False,
        visual_fallback_generate_diagrams=True,
        web_image_search_enabled=True,
        pexels_api_key="test-key",
        web_image_search_persist_to_library=False,
        project_storage_path=tmp_path,
    )
    service = VisualFallbackService(db_session, settings=settings)

    class FakeWebSearch:
        def resolve_requirement(self, slide, requirement, requirement_index, *, output_dir, facts=None):
            return FallbackImage(
                path=web_file,
                generated=True,
                web_sourced=True,
                attribution="Photo by Alex on Pexels",
                source_url="https://www.pexels.com/photo/1/",
            )

    service._web_search = FakeWebSearch()  # type: ignore[assignment]

    resolved = service.resolve_export_images(
        project_id,  # type: ignore[arg-type]
        [slide],
        output_dir=tmp_path / "presentation",
        base_paths={},
    )
    result = resolved[(slide.id, 0)]
    assert result.web_sourced is True
    assert result.path == web_file
