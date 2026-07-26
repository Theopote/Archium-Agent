"""Topic 06 P3 — DesignArtifact identity on Vision Assets (DOM-027)."""

from __future__ import annotations

from uuid import uuid4

from archium.domain.architectural_asset import (
    ArchitecturalAssetRole,
    architectural_asset_from_parts,
)
from archium.domain.asset import Asset
from archium.domain.design_artifact import (
    DesignArtifactKind,
    build_design_artifact,
    design_artifact_from_asset,
    design_artifact_kind_from_image_type,
)
from archium.domain.enums import AssetType
from archium.domain.knowledge_reference import KnowledgeUsage
from archium.domain.visual.vision_generation import ArchitectureImageType


def test_kind_mapping_from_image_type() -> None:
    assert (
        design_artifact_kind_from_image_type(ArchitectureImageType.CONCEPT_SKETCH)
        == DesignArtifactKind.CONCEPT
    )
    assert (
        design_artifact_kind_from_image_type(ArchitectureImageType.SITE_DIAGRAM)
        == DesignArtifactKind.DIAGRAM
    )
    assert (
        design_artifact_kind_from_image_type(ArchitectureImageType.ATMOSPHERE_IMAGE)
        == DesignArtifactKind.ATMOSPHERE
    )


def test_design_artifact_round_trip_on_asset_metadata() -> None:
    project_id = uuid4()
    direction_id = uuid4()
    brief_id = uuid4()
    artifact = build_design_artifact(
        project_id=project_id,
        image_type=ArchitectureImageType.FLOW_DIAGRAM,
        concept_direction_id=direction_id,
        visual_concept_brief_id=brief_id,
        seed_source="concept_direction+deck_lock",
        prompt_hash="abc123",
    )
    asset = Asset(
        id=uuid4(),
        project_id=project_id,
        filename="vision.png",
        path="/tmp/vision.png",
        asset_type=AssetType.PHOTO,
        tags=["ai_generated", "illustrative"],
        metadata={
            "origin": "ai_generated",
            "asset_policy": "illustrative_only",
            "image_type": "flow_diagram",
            **artifact.to_metadata(),
        },
    )
    # Stamp asset_id as persist does
    nested = dict(asset.metadata["design_artifact"])
    nested["asset_id"] = str(asset.id)
    asset.metadata["design_artifact"] = nested

    loaded = design_artifact_from_asset(asset)
    assert loaded is not None
    assert loaded.id == artifact.id
    assert loaded.kind == DesignArtifactKind.DIAGRAM
    assert loaded.concept_direction_id == direction_id
    assert loaded.visual_concept_brief_id == brief_id
    assert loaded.illustrative is True
    assert loaded.seed_source.startswith("concept_direction")


def test_design_artifact_stays_illustrative_via_topic05_facade() -> None:
    project_id = uuid4()
    artifact = build_design_artifact(
        project_id=project_id,
        image_type=ArchitectureImageType.ATMOSPHERE_IMAGE,
        seed_source="brief",
    )
    asset = Asset(
        id=uuid4(),
        project_id=project_id,
        filename="atm.png",
        path="/tmp/atm.png",
        asset_type=AssetType.PHOTO,
        tags=["ai_generated", "illustrative"],
        metadata={
            "origin": "ai_generated",
            "asset_policy": "illustrative_only",
            **artifact.to_metadata(),
        },
    )
    facade = architectural_asset_from_parts(asset)
    assert facade.role == ArchitecturalAssetRole.REFERENCE
    assert facade.usage == KnowledgeUsage.ILLUSTRATIVE


def test_design_artifact_kind_not_presentation_artifact_kind() -> None:
    from archium.domain.artifact_ownership import ArtifactKind

    design_values = {k.value for k in DesignArtifactKind}
    presentation_values = {k.value for k in ArtifactKind}
    assert design_values.isdisjoint(presentation_values)
