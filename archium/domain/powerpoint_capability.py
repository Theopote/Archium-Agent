"""Explicit mapping from canonical RenderScene nodes to PowerPoint objects."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from archium.domain._base import DomainModel


class PowerPointFidelity(StrEnum):
    """How faithfully an authored scene construct survives PPTX compilation."""

    NATIVE_STABLE = "native_stable"
    NATIVE_NORMALIZED = "native_normalized"
    APPROXIMATE = "approximate"
    BAKE_REQUIRED = "bake_required"
    PACKAGE_SIDECAR = "package_sidecar"
    DIRECT_PRESERVATION = "direct_preservation"
    UNSUPPORTED = "unsupported"


class PowerPointCapabilityMapping(DomainModel):
    scene_node_type: str = Field(min_length=1)
    pptx_object_type: str = Field(min_length=1)
    fidelity: PowerPointFidelity
    limitations: list[str] = Field(default_factory=list)
    validation_rules: list[str] = Field(default_factory=list)


RENDER_SCENE_V1_CAPABILITIES: dict[str, PowerPointCapabilityMapping] = {
    "text": PowerPointCapabilityMapping(
        scene_node_type="text",
        pptx_object_type="p:sp + p:txBody",
        fidelity=PowerPointFidelity.NATIVE_STABLE,
        limitations=["Host font substitution may change line wrapping."],
        validation_rules=["node_identity_preserved", "text_content_preserved"],
    ),
    "shape": PowerPointCapabilityMapping(
        scene_node_type="shape",
        pptx_object_type="p:sp",
        fidelity=PowerPointFidelity.NATIVE_NORMALIZED,
        limitations=["V1 supports rectangle, ellipse, line, and card only."],
        validation_rules=["node_identity_preserved", "geometry_within_tolerance"],
    ),
    "image": PowerPointCapabilityMapping(
        scene_node_type="image",
        pptx_object_type="p:pic",
        fidelity=PowerPointFidelity.NATIVE_STABLE,
        limitations=["Source pixels remain raster even though the picture object is native."],
        validation_rules=["node_identity_preserved", "asset_resolved"],
    ),
    "drawing": PowerPointCapabilityMapping(
        scene_node_type="drawing",
        pptx_object_type="p:pic",
        fidelity=PowerPointFidelity.NATIVE_STABLE,
        limitations=["V1 preserves the architectural drawing as a picture object."],
        validation_rules=["node_identity_preserved", "asset_resolved", "drawing_crop_policy"],
    ),
}


def capability_for_scene_node(node_type: str) -> PowerPointCapabilityMapping:
    """Return the declared contract; unknown constructs fail closed."""
    try:
        return RENDER_SCENE_V1_CAPABILITIES[node_type]
    except KeyError as exc:
        raise ValueError(f"No PowerPoint capability mapping for scene node type: {node_type}") from exc

