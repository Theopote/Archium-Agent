"""Tests for Studio semantic evidence item editing."""

from __future__ import annotations

from uuid import uuid4

import pytest
from archium.application.slide_evidence_edit_service import SlideEvidenceEditService
from archium.domain.enums import ProjectType, VisualType
from archium.domain.presentation import Presentation
from archium.domain.project import Project
from archium.domain.slide import SlideSpec, VisualRequirement
from archium.domain.visual.layout_evidence_item import EvidenceItemRole, LayoutEvidenceItem
from archium.infrastructure.database.repositories import (
    PresentationRepository,
    ProjectRepository,
)
from sqlalchemy.orm import Session


@pytest.fixture
def presentation_id(db_session: Session) -> object:
    project_id = ProjectRepository(db_session).create(
        Project(name="Evidence Edit", project_type=ProjectType.HEALTHCARE)
    ).id
    return PresentationRepository(db_session).create_presentation(
        Presentation(project_id=project_id, title="Deck")
    ).id


def test_save_evidence_items_updates_slide_and_requirements(
    db_session: Session,
    presentation_id: object,
) -> None:
    photo_a = uuid4()
    photo_b = uuid4()
    pres_repo = PresentationRepository(db_session)
    slide = pres_repo.save_slide(
        SlideSpec(
            presentation_id=presentation_id,  # type: ignore[arg-type]
            chapter_id="site",
            order=1,
            title="现场问题",
            message="入口混行影响到达体验。",
            visual_requirements=[
                VisualRequirement(type=VisualType.SITE_PHOTO, description="旧描述 1"),
                VisualRequirement(type=VisualType.SITE_PHOTO, description="旧描述 2"),
            ],
        )
    )
    service = SlideEvidenceEditService(db_session)
    result = service.save_evidence_items(
        slide.id,
        [
            LayoutEvidenceItem(
                claim="入口混行导致人车冲突",
                role=EvidenceItemRole.PRIMARY,
                asset=str(photo_a),
            ),
            LayoutEvidenceItem(
                claim="停车占道压缩人行空间",
                role=EvidenceItemRole.SUPPORTING,
                asset=str(photo_b),
            ),
        ],
    )
    assert result.slide.key_points == [
        "入口混行导致人车冲突",
        "停车占道压缩人行空间",
    ]
    photo_reqs = [
        req for req in result.slide.visual_requirements if req.type == VisualType.SITE_PHOTO
    ]
    assert photo_reqs[0].preferred_asset_ids == [photo_a]
    assert photo_reqs[1].preferred_asset_ids == [photo_b]


def test_sync_asset_from_photo_element(
    db_session: Session,
    presentation_id: object,
) -> None:
    asset_id = uuid4()
    pres_repo = PresentationRepository(db_session)
    slide = pres_repo.save_slide(
        SlideSpec(
            presentation_id=presentation_id,  # type: ignore[arg-type]
            chapter_id="site",
            order=1,
            title="现场问题",
            message="入口混行影响到达体验。",
            evidence_items=[
                LayoutEvidenceItem(claim="入口混行", role=EvidenceItemRole.PRIMARY),
            ],
        )
    )
    service = SlideEvidenceEditService(db_session)
    updated = service.sync_asset_from_photo_element(
        slide.id,
        element_id="photo_0",
        asset_id=asset_id,
    )
    assert updated is not None
    assert updated.evidence_items[0].asset == str(asset_id)
