"""DesignArtifact — thin design-product identity (Topic 06 P3 / DOM-027).

Separate from presentation ``ArtifactKind`` / ArtifactJob. Pixels stay on Asset;
this VO is stamped into Asset.metadata for project_id + direction lineage.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import Field

from archium.domain._base import IdentifiedModel
from archium.domain.asset import Asset
from archium.domain.visual.vision_generation import ArchitectureImageType

DESIGN_ARTIFACT_META_KEY = "design_artifact"


class DesignArtifactKind(StrEnum):
    """Design output kinds — NOT presentation ArtifactKind values."""

    CONCEPT = "concept"
    DIAGRAM = "diagram"
    ATMOSPHERE = "atmosphere"
    MATERIAL = "material"


_IMAGE_TYPE_TO_KIND: dict[ArchitectureImageType, DesignArtifactKind] = {
    ArchitectureImageType.CONCEPT_SKETCH: DesignArtifactKind.CONCEPT,
    ArchitectureImageType.PRESENTATION_ILLUSTRATION: DesignArtifactKind.CONCEPT,
    ArchitectureImageType.SKETCH_NOTE: DesignArtifactKind.CONCEPT,
    ArchitectureImageType.SITE_DIAGRAM: DesignArtifactKind.DIAGRAM,
    ArchitectureImageType.FLOW_DIAGRAM: DesignArtifactKind.DIAGRAM,
    ArchitectureImageType.SECTION_ILLUSTRATION: DesignArtifactKind.DIAGRAM,
    ArchitectureImageType.ATMOSPHERE_IMAGE: DesignArtifactKind.ATMOSPHERE,
    ArchitectureImageType.MATERIAL_STUDY: DesignArtifactKind.MATERIAL,
}


class DesignArtifact(IdentifiedModel):
    """Addressable design visual product linked to an illustrative Asset."""

    project_id: UUID
    kind: DesignArtifactKind = DesignArtifactKind.CONCEPT
    asset_id: UUID | None = None
    concept_direction_id: UUID | None = None
    visual_concept_brief_id: UUID | None = None
    image_type: str = ""
    seed_source: str = Field(default="", max_length=40)
    prompt_hash: str = ""
    illustrative: bool = True

    def to_metadata(self) -> dict[str, Any]:
        return {
            DESIGN_ARTIFACT_META_KEY: {
                "id": str(self.id),
                "project_id": str(self.project_id),
                "kind": self.kind.value,
                "asset_id": str(self.asset_id) if self.asset_id else None,
                "concept_direction_id": (
                    str(self.concept_direction_id) if self.concept_direction_id else None
                ),
                "visual_concept_brief_id": (
                    str(self.visual_concept_brief_id)
                    if self.visual_concept_brief_id
                    else None
                ),
                "image_type": self.image_type,
                "seed_source": self.seed_source,
                "prompt_hash": self.prompt_hash,
                "illustrative": True,
            },
            # Flat mirrors for cheap filters / Topic 05 facade hints
            "design_artifact_id": str(self.id),
            "design_artifact_kind": self.kind.value,
            "direction_id": (
                str(self.concept_direction_id) if self.concept_direction_id else None
            ),
        }


def design_artifact_kind_from_image_type(
    image_type: ArchitectureImageType | str,
) -> DesignArtifactKind:
    if isinstance(image_type, str):
        try:
            image_type = ArchitectureImageType(image_type)
        except ValueError:
            return DesignArtifactKind.CONCEPT
    return _IMAGE_TYPE_TO_KIND.get(image_type, DesignArtifactKind.CONCEPT)


def build_design_artifact(
    *,
    project_id: UUID,
    asset_id: UUID | None = None,
    image_type: ArchitectureImageType | str = "",
    concept_direction_id: UUID | None = None,
    visual_concept_brief_id: UUID | None = None,
    seed_source: str = "",
    prompt_hash: str = "",
    artifact_id: UUID | None = None,
) -> DesignArtifact:
    return DesignArtifact(
        id=artifact_id or uuid4(),
        project_id=project_id,
        kind=design_artifact_kind_from_image_type(image_type),
        asset_id=asset_id,
        concept_direction_id=concept_direction_id,
        visual_concept_brief_id=visual_concept_brief_id,
        image_type=(
            image_type.value
            if isinstance(image_type, ArchitectureImageType)
            else str(image_type or "")
        ),
        seed_source=(seed_source or "")[:40],
        prompt_hash=prompt_hash or "",
        illustrative=True,
    )


def design_artifact_from_asset(asset: Asset | None) -> DesignArtifact | None:
    """Reconstruct DesignArtifact from Asset.metadata (None if missing)."""
    if asset is None:
        return None
    meta = asset.metadata if isinstance(asset.metadata, dict) else {}
    nested = meta.get(DESIGN_ARTIFACT_META_KEY)
    if isinstance(nested, dict) and nested.get("id"):
        try:
            return DesignArtifact(
                id=UUID(str(nested["id"])),
                project_id=UUID(str(nested.get("project_id") or asset.project_id)),
                kind=DesignArtifactKind(str(nested.get("kind") or "concept")),
                asset_id=(
                    UUID(str(nested["asset_id"]))
                    if nested.get("asset_id")
                    else asset.id
                ),
                concept_direction_id=(
                    UUID(str(nested["concept_direction_id"]))
                    if nested.get("concept_direction_id")
                    else None
                ),
                visual_concept_brief_id=(
                    UUID(str(nested["visual_concept_brief_id"]))
                    if nested.get("visual_concept_brief_id")
                    else None
                ),
                image_type=str(nested.get("image_type") or ""),
                seed_source=str(nested.get("seed_source") or "")[:40],
                prompt_hash=str(nested.get("prompt_hash") or ""),
                illustrative=bool(nested.get("illustrative", True)),
            )
        except (TypeError, ValueError):
            return None
    raw_id = meta.get("design_artifact_id")
    if not raw_id:
        return None
    try:
        return DesignArtifact(
            id=UUID(str(raw_id)),
            project_id=asset.project_id,
            kind=DesignArtifactKind(str(meta.get("design_artifact_kind") or "concept")),
            asset_id=asset.id,
            concept_direction_id=(
                UUID(str(meta["direction_id"])) if meta.get("direction_id") else None
            ),
            image_type=str(meta.get("image_type") or ""),
            seed_source=str(meta.get("seed_source") or "")[:40],
            prompt_hash=str(meta.get("prompt_hash") or ""),
            illustrative=True,
        )
    except (TypeError, ValueError):
        return None
