"""Tests for semantic evidence item asset binding."""

from __future__ import annotations

from uuid import uuid4

import pytest
from archium.application.asset_matching_service import AssetMatchingService
from archium.application.evidence_item_binding_service import bind_slide_evidence_items
from archium.domain.asset import Asset
from archium.domain.asset_presentation_readiness import (
    ASSET_PRESENTATION_READINESS_KEY,
    AssetPresentationReadiness,
    AssetPresentationRole,
)
from archium.domain.enums import AssetType, ProjectType, VisualType
from archium.domain.presentation import Presentation
from archium.domain.project import Project
from archium.domain.slide import SlideSpec, VisualRequirement
from archium.domain.visual.layout_evidence_item import EvidenceItemRole, LayoutEvidenceItem
from archium.infrastructure.database.repositories import (
    AssetRepository,
    PresentationRepository,
    ProjectRepository,
)
from sqlalchemy.orm import Session


def _photo_asset(
    project_id,
    *,
    filename: str,
    description: str,
) -> Asset:
    readiness = AssetPresentationReadiness(
        pixel_analyzed=True,
        presentation_ready=True,
        visual_information_density=0.75,
        readable_at_slide_scale=True,
        recommended_role=AssetPresentationRole.EVIDENCE_SUPPORTING,
    )
    return Asset(
        project_id=project_id,
        filename=filename,
        path=f"/tmp/{filename}",
        asset_type=AssetType.PHOTO,
        description=description,
        tags=["site_photo"],
        quality_score=0.85,
        width=1600,
        height=1200,
        metadata={ASSET_PRESENTATION_READINESS_KEY: readiness.to_metadata()},
    )


@pytest.fixture
def project_id(db_session: Session) -> object:
    return ProjectRepository(db_session).create(
        Project(name="Evidence Binding Project", project_type=ProjectType.HEALTHCARE)
    ).id


def test_bind_slide_evidence_items_uses_matched_requirements() -> None:
    photo_a = uuid4()
    photo_b = uuid4()
    slide = SlideSpec(
        presentation_id=uuid4(),
        chapter_id="site",
        order=1,
        title="现场问题",
        message="入口混行影响到达体验。",
        evidence_items=[
            LayoutEvidenceItem(claim="入口混行", role=EvidenceItemRole.PRIMARY),
            LayoutEvidenceItem(claim="停车占道", role=EvidenceItemRole.SUPPORTING),
        ],
        visual_requirements=[
            VisualRequirement(
                type=VisualType.SITE_PHOTO,
                description="入口照片",
                preferred_asset_ids=[photo_a],
            ),
            VisualRequirement(
                type=VisualType.SITE_PHOTO,
                description="路缘照片",
                preferred_asset_ids=[photo_b],
            ),
        ],
    )
    assets = [
        Asset(
            project_id=uuid4(),
            id=photo_a,
            filename="entry.jpg",
            path="/tmp/entry.jpg",
            asset_type=AssetType.PHOTO,
            description="入口混行",
        ),
        Asset(
            project_id=uuid4(),
            id=photo_b,
            filename="curb.jpg",
            path="/tmp/curb.jpg",
            asset_type=AssetType.PHOTO,
            description="停车占道",
        ),
    ]

    bound, changed = bind_slide_evidence_items(slide, assets)

    assert changed is True
    assert bound.evidence_items[0].asset == str(photo_a)
    assert bound.evidence_items[1].asset == str(photo_b)


def test_match_presentation_slides_binds_evidence_items(
    db_session: Session,
    project_id: object,
) -> None:
    asset_repo = AssetRepository(db_session)
    entry = asset_repo.create(
        _photo_asset(
            project_id,
            filename="entry.jpg",
            description="入口混行导致患者与车流交织",
        )
    )
    curb = asset_repo.create(
        _photo_asset(
            project_id,
            filename="curb.jpg",
            description="停车占道压缩人行空间",
        )
    )

    pres_repo = PresentationRepository(db_session)
    presentation = pres_repo.create_presentation(
        Presentation(project_id=project_id, title="Evidence Deck")  # type: ignore[arg-type]
    )
    pres_repo.save_slide(
        SlideSpec(
            presentation_id=presentation.id,
            chapter_id="site",
            order=1,
            title="交通问题",
            message="入口混行影响到达体验。",
            evidence_items=[
                LayoutEvidenceItem(
                    claim="入口混行导致患者与车流交织",
                    role=EvidenceItemRole.PRIMARY,
                ),
                LayoutEvidenceItem(
                    claim="停车占道压缩人行空间",
                    role=EvidenceItemRole.SUPPORTING,
                ),
            ],
            visual_requirements=[
                VisualRequirement(
                    type=VisualType.SITE_PHOTO,
                    description="入口混行导致患者与车流交织",
                    required=True,
                ),
                VisualRequirement(
                    type=VisualType.SITE_PHOTO,
                    description="停车占道压缩人行空间",
                    required=True,
                ),
            ],
        )
    )

    matcher = AssetMatchingService(db_session)
    updated, count = matcher.match_presentation_slides(
        project_id,  # type: ignore[arg-type]
        presentation.id,
    )

    assert count >= 2
    assert updated[0].evidence_items[0].asset == str(entry.id)
    assert updated[0].evidence_items[1].asset == str(curb.id)
