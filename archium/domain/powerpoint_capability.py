"""Explicit mapping from canonical RenderScene nodes to PowerPoint objects."""

from __future__ import annotations

from enum import StrEnum
from typing import cast

from pydantic import Field

from archium.domain._base import DomainModel
from archium.domain.visual.render_scene import BaseRenderNode, ImageNode, ShapeNode


class PowerPointFidelity(StrEnum):
    """How faithfully an authored scene construct survives PPTX compilation."""

    NATIVE_STABLE = "native_stable"
    NATIVE_NORMALIZED = "native_normalized"
    APPROXIMATE = "approximate"
    BAKE_REQUIRED = "bake_required"
    PACKAGE_SIDECAR = "package_sidecar"
    DIRECT_PRESERVATION = "direct_preservation"
    UNSUPPORTED = "unsupported"


class MappingCardinality(StrEnum):
    ONE_TO_ONE = "one_to_one"
    ONE_TO_MANY = "one_to_many"
    MANY_TO_ONE = "many_to_one"


class PowerPointCapabilityMapping(DomainModel):
    scene_node_type: str = Field(min_length=1)
    pptx_object_type: str = Field(min_length=1)
    fidelity: PowerPointFidelity
    mapping_cardinality: MappingCardinality = MappingCardinality.ONE_TO_ONE
    limitations: list[str] = Field(default_factory=list)
    validation_rules: list[str] = Field(default_factory=list)


class PowerPointNodeAssessment(DomainModel):
    node_id: str = Field(min_length=1)
    node_type: str = Field(min_length=1)
    mapping: PowerPointCapabilityMapping
    detected_features: list[str] = Field(default_factory=list)


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


def capability_for_scene_node(node: str | BaseRenderNode) -> PowerPointCapabilityMapping:
    """Resolve fidelity from a node instance, or return the type-level baseline."""
    node_type = node if isinstance(node, str) else node.node_type
    try:
        baseline = RENDER_SCENE_V1_CAPABILITIES[node_type]
    except KeyError as exc:
        raise ValueError(f"No PowerPoint capability mapping for scene node type: {node_type}") from exc
    if isinstance(node, str):
        return baseline

    fidelity = baseline.fidelity
    limitations = list(baseline.limitations)
    if node.rotation != 0 or node.opacity != 1:
        fidelity = PowerPointFidelity.APPROXIMATE
        limitations.append("V1 PPTX instructions do not preserve node rotation or opacity.")

    if isinstance(node, ShapeNode):
        if node.shape_kind == "rectangle" and node.corner_radius == 0 and fidelity != PowerPointFidelity.APPROXIMATE:
            fidelity = PowerPointFidelity.NATIVE_STABLE
        elif node.shape_kind != "rectangle" or node.corner_radius > 0:
            fidelity = PowerPointFidelity.APPROXIMATE
            limitations.append(
                f"V1 PptxGenJS backend normalizes {node.shape_kind} geometry to a rectangle."
            )

    if isinstance(node, ImageNode) and (node.corner_radius or node.border or node.shadow):
        fidelity = PowerPointFidelity.APPROXIMATE
        limitations.append("V1 PPTX picture export does not preserve corner, border, or shadow styling.")

    return cast(
        PowerPointCapabilityMapping,
        baseline.model_copy(
            update={"fidelity": fidelity, "limitations": list(dict.fromkeys(limitations))}
        ),
    )


def assess_scene_node(node: BaseRenderNode) -> PowerPointNodeAssessment:
    features = [f"rotation:{node.rotation}"] if node.rotation else []
    if node.opacity != 1:
        features.append(f"opacity:{node.opacity}")
    if isinstance(node, ShapeNode):
        features.append(f"shape_kind:{node.shape_kind}")
        if node.corner_radius:
            features.append(f"corner_radius:{node.corner_radius}")
    if isinstance(node, ImageNode):
        features.append(f"fit_mode:{node.fit_mode}")
        if node.shadow:
            features.append("shadow")
        if node.border:
            features.append("border")
    return PowerPointNodeAssessment(
        node_id=node.id,
        node_type=node.node_type,
        mapping=capability_for_scene_node(node),
        detected_features=features,
    )
