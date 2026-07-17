"""Unit tests for asset matching."""

from __future__ import annotations

from uuid import uuid4

import pytest
from archium.application.asset_matching_service import AssetMatchingService
from archium.domain.asset import Asset
from archium.domain.enums import AssetType, ProjectType, VisualType
from archium.domain.presentation import Presentation
from archium.domain.project import Project
from archium.domain.slide import SlideSpec, VisualRequirement
from archium.infrastructure.database.repositories import (
    AssetRepository,
    PresentationRepository,
    ProjectRepository,
)
from sqlalchemy.orm import Session


@pytest.fixture
def project_id(db_session: Session) -> object:
    return ProjectRepository(db_session).create(
        Project(name="Asset Match Project", project_type=ProjectType.HEALTHCARE)
    ).id


def test_match_assets_links_visual_requirement(
    db_session: Session,
    project_id: object,
) -> None:
    asset_repo = AssetRepository(db_session)
    asset = asset_repo.create(
        Asset(
            project_id=project_id,  # type: ignore[arg-type]
            filename="site_plan.png",
            path="/tmp/site_plan.png",
            asset_type=AssetType.DRAWING,
            description="总平面图交通流线",
            tags=["site_plan", "drawing"],
            quality_score=0.9,
        )
    )

    pres_repo = PresentationRepository(db_session)
    presentation = pres_repo.create_presentation(
        Presentation(project_id=project_id, title="Test")  # type: ignore[arg-type]
    )
    pres_repo.save_slide(
        SlideSpec(
            presentation_id=presentation.id,
            chapter_id="ch1",
            order=0,
            title="院区现状",
            message="交通组织存在问题",
            visual_requirements=[
                VisualRequirement(
                    type=VisualType.SITE_PLAN,
                    description="总平面图标注交通流线",
                    required=True,
                )
            ],
        )
    )

    matcher = AssetMatchingService(db_session)
    updated, count = matcher.match_presentation_slides(
        project_id,  # type: ignore[arg-type]
        presentation.id,
    )

    assert count == 1
    assert updated[0].visual_requirements[0].preferred_asset_ids == [asset.id]


def test_match_assets_skips_existing_ids(db_session: Session, project_id: object) -> None:
    existing_id = uuid4()
    pres_repo = PresentationRepository(db_session)
    presentation = pres_repo.create_presentation(
        Presentation(project_id=project_id, title="Test")  # type: ignore[arg-type]
    )
    pres_repo.save_slide(
        SlideSpec(
            presentation_id=presentation.id,
            chapter_id="ch1",
            order=0,
            title="现状",
            message="问题描述",
            visual_requirements=[
                VisualRequirement(
                    type=VisualType.DIAGRAM,
                    description="示意",
                    preferred_asset_ids=[existing_id],
                )
            ],
        )
    )

    matcher = AssetMatchingService(db_session)
    _, count = matcher.match_presentation_slides(project_id, presentation.id)  # type: ignore[arg-type]

    assert count == 1
