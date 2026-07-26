"""Topic 07 L3 — Presentation.mission_id + DesignArtifact catalog."""

from __future__ import annotations

from uuid import uuid4

from archium.application.design_artifact_catalog import list_design_artifacts
from archium.application.presentation_models import PresentationRequest
from archium.domain.asset import Asset
from archium.domain.design_artifact import build_design_artifact
from archium.domain.enums import AssetType, PresentationType
from archium.domain.presentation import Presentation
from archium.workflow.serialization import request_from_dict, request_to_dict


def test_presentation_domain_accepts_mission_id() -> None:
    mission_id = uuid4()
    presentation = Presentation(
        project_id=uuid4(),
        title="溯源汇报",
        mission_id=mission_id,
    )
    assert presentation.mission_id == mission_id


def test_request_round_trip_keeps_mission_id() -> None:
    mission_id = uuid4()
    request = PresentationRequest(
        title="t",
        audience="a",
        purpose="p",
        presentation_type=PresentationType.CONCEPT,
        mission_id=mission_id,
    )
    data = request_to_dict(request)
    assert data["mission_id"] == str(mission_id)
    restored = request_from_dict(data)
    assert restored.mission_id == mission_id


def test_list_design_artifacts_filters_stamped_assets() -> None:
    project_id = uuid4()
    stamped = build_design_artifact(
        project_id=project_id,
        image_type="atmosphere_image",
        seed_source="brief",
    )
    assets = [
        Asset(
            id=uuid4(),
            project_id=project_id,
            filename="photo.jpg",
            path="/tmp/photo.jpg",
            asset_type=AssetType.PHOTO,
            metadata={},
        ),
        Asset(
            id=uuid4(),
            project_id=project_id,
            filename="vision.png",
            path="/tmp/vision.png",
            asset_type=AssetType.PHOTO,
            tags=["ai_generated", "illustrative"],
            metadata={
                "origin": "ai_generated",
                "asset_policy": "illustrative_only",
                **stamped.to_metadata(),
            },
        ),
    ]

    class _Assets:
        def list_by_project(self, _pid):
            return assets

    class _Session:
        pass

    # Patch repository via monkey-style local wrapper
    import archium.application.design_artifact_catalog as catalog

    original = catalog.AssetRepository
    catalog.AssetRepository = lambda _session: _Assets()  # type: ignore[misc,assignment]
    try:
        rows = list_design_artifacts(_Session(), project_id, limit=10)
    finally:
        catalog.AssetRepository = original

    assert len(rows) == 1
    assert rows[0].artifact.kind.value == "atmosphere"
    assert "vision.png" in rows[0].display_line()
