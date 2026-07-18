"""Unit tests for asset metadata service."""

from __future__ import annotations

from uuid import uuid4

import pytest
from archium.application.asset_metadata_service import AssetMetadataService
from archium.domain.asset import Asset
from archium.domain.enums import AssetType, ProjectType
from archium.domain.plan_overlay import (
    PLAN_NORTH_ARROW_KEY,
    PLAN_SCALE_LABEL_KEY,
    PlanOverlayMetadata,
)
from archium.domain.project import Project
from archium.exceptions import WorkflowError
from archium.infrastructure.database.repositories import AssetRepository, ProjectRepository
from sqlalchemy.orm import Session


@pytest.fixture
def project_id(db_session: Session) -> object:
    return ProjectRepository(db_session).create(
        Project(name="Metadata Project", project_type=ProjectType.HEALTHCARE)
    ).id


def test_save_and_load_plan_overlay(db_session: Session, project_id: object) -> None:
    asset = AssetRepository(db_session).create(
        Asset(
            project_id=project_id,  # type: ignore[arg-type]
            filename="site_plan.png",
            path="/tmp/site_plan.png",
            asset_type=AssetType.DRAWING,
        )
    )
    service = AssetMetadataService(db_session)
    saved = service.save_plan_overlay(
        asset.id,
        PlanOverlayMetadata(
            show_north_arrow=True,
            scale_label="0 — 100m",
            legend_items=[],
        ),
    )
    assert saved.metadata[PLAN_NORTH_ARROW_KEY] is True
    assert saved.metadata[PLAN_SCALE_LABEL_KEY] == "0 — 100m"

    loaded = service.get_plan_overlay(asset.id)
    assert loaded.show_north_arrow is True
    assert loaded.scale_label == "0 — 100m"


def test_clear_plan_overlay(db_session: Session, project_id: object) -> None:
    asset = AssetRepository(db_session).create(
        Asset(
            project_id=project_id,  # type: ignore[arg-type]
            filename="site_plan.png",
            path="/tmp/site_plan.png",
            asset_type=AssetType.DRAWING,
            metadata={PLAN_NORTH_ARROW_KEY: True},
        )
    )
    service = AssetMetadataService(db_session)
    cleared = service.clear_plan_overlay(asset.id)
    assert PLAN_NORTH_ARROW_KEY not in cleared.metadata


def test_save_plan_overlay_missing_asset_raises(db_session: Session) -> None:
    service = AssetMetadataService(db_session)
    with pytest.raises(WorkflowError):
        service.save_plan_overlay(uuid4(), PlanOverlayMetadata(show_north_arrow=True))
