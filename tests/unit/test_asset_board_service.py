"""Unit tests for Asset Board service."""

from __future__ import annotations

import pytest
from archium.application.asset_board_service import AssetBoardService
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
def board_context(db_session: Session) -> tuple[object, object, object]:
    project_id = ProjectRepository(db_session).create(
        Project(name="Asset Board Project", project_type=ProjectType.HEALTHCARE)
    ).id
    presentation_id = PresentationRepository(db_session).create_presentation(
        Presentation(project_id=project_id, title="Board Test")  # type: ignore[arg-type]
    ).id
    asset_id = AssetRepository(db_session).create(
        Asset(
            project_id=project_id,  # type: ignore[arg-type]
            filename="site_plan.png",
            path="/tmp/site_plan.png",
            asset_type=AssetType.DRAWING,
            description="总平面图",
            tags=["site_plan"],
            width=1920,
            height=1080,
        )
    ).id
    return project_id, presentation_id, asset_id


def test_build_board_lists_visual_requirements(
    db_session: Session,
    board_context: tuple[object, object, object],
) -> None:
    project_id, presentation_id, asset_id = board_context
    pres_repo = PresentationRepository(db_session)
    pres_repo.save_slide(
        SlideSpec(
            presentation_id=presentation_id,  # type: ignore[arg-type]
            chapter_id="ch1",
            order=0,
            title="总图",
            message="交通组织",
            visual_requirements=[
                VisualRequirement(
                    type=VisualType.SITE_PLAN,
                    description="总平面图",
                    required=True,
                    preferred_asset_ids=[asset_id],  # type: ignore[list-item]
                    match_score=0.85,
                )
            ],
        )
    )

    view = AssetBoardService(db_session).build_board(
        project_id,  # type: ignore[arg-type]
        presentation_id,  # type: ignore[arg-type]
    )

    assert len(view.rows) == 1
    row = view.rows[0]
    assert row.visual_type == VisualType.SITE_PLAN.value
    assert row.candidate_asset_id == asset_id
    assert row.match_score == 0.85
    assert view.matched_count == 1
    assert view.pending_count == 1


def test_assign_and_confirm_asset(
    db_session: Session,
    board_context: tuple[object, object, object],
) -> None:
    project_id, presentation_id, asset_id = board_context
    pres_repo = PresentationRepository(db_session)
    slide = pres_repo.save_slide(
        SlideSpec(
            presentation_id=presentation_id,  # type: ignore[arg-type]
            chapter_id="ch1",
            order=0,
            title="现状",
            message="问题描述",
            visual_requirements=[
                VisualRequirement(
                    type=VisualType.DIAGRAM,
                    description="示意",
                    required=True,
                )
            ],
        )
    )

    service = AssetBoardService(db_session)
    updated = service.assign_asset(slide.id, 0, asset_id)  # type: ignore[arg-type]
    assert updated.visual_requirements[0].preferred_asset_ids == [asset_id]

    confirmed = service.confirm_assignment(slide.id, 0)
    assert confirmed.visual_requirements[0].confirmed is True

    view = service.build_board(
        project_id,  # type: ignore[arg-type]
        presentation_id,  # type: ignore[arg-type]
    )
    assert view.confirmed_count == 1
    assert view.pending_count == 0


def test_rematch_refreshes_board(
    db_session: Session,
    board_context: tuple[object, object, object],
) -> None:
    project_id, presentation_id, _asset_id = board_context
    pres_repo = PresentationRepository(db_session)
    pres_repo.save_slide(
        SlideSpec(
            presentation_id=presentation_id,  # type: ignore[arg-type]
            chapter_id="ch1",
            order=0,
            title="总图",
            message="交通组织",
            visual_requirements=[
                VisualRequirement(
                    type=VisualType.SITE_PLAN,
                    description="总平面图标注交通流线",
                    required=True,
                )
            ],
        )
    )

    view = AssetBoardService(db_session).rematch(
        project_id,  # type: ignore[arg-type]
        presentation_id,  # type: ignore[arg-type]
    )

    assert view.matched_count == 1
    assert view.rows[0].candidate_asset_id is not None


def test_build_board_marks_web_import_provenance_and_eligibility(
    db_session: Session,
    board_context: tuple[object, object, object],
) -> None:
    project_id, presentation_id, asset_id = board_context
    AssetRepository(db_session).update(
        AssetRepository(db_session).get_by_id(asset_id).model_copy(  # type: ignore[union-attr]
            update={
                "tags": ["web_import", "pexels"],
                "metadata": {
                    "provider": "pexels",
                    "attribution": "Photo by Alex on Pexels",
                },
            }
        )
    )
    pres_repo = PresentationRepository(db_session)
    pres_repo.save_slide(
        SlideSpec(
            presentation_id=presentation_id,  # type: ignore[arg-type]
            chapter_id="ch1",
            order=0,
            title="效果图",
            message="入口",
            visual_requirements=[
                VisualRequirement(
                    type=VisualType.RENDERING,
                    description="透视",
                    required=True,
                    preferred_asset_ids=[asset_id],  # type: ignore[list-item]
                )
            ],
        )
    )
    pres_repo.save_slide(
        SlideSpec(
            presentation_id=presentation_id,  # type: ignore[arg-type]
            chapter_id="ch1",
            order=1,
            title="另一页",
            message="无素材",
            visual_requirements=[
                VisualRequirement(
                    type=VisualType.SITE_PHOTO,
                    description="现场",
                    required=True,
                )
            ],
        )
    )

    rows = AssetBoardService(db_session).build_board(
        project_id,  # type: ignore[arg-type]
        presentation_id,  # type: ignore[arg-type]
    ).rows
    matched = next(row for row in rows if row.candidate_asset_id == asset_id)
    assert matched.asset_source is not None
    assert "网络搜图" in matched.asset_source
    assert "pexels" in matched.asset_source

    missing = next(row for row in rows if row.candidate_asset_id is None)
    assert missing.web_search_eligible is True
