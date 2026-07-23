"""Explicit mapping from canonical RenderScene nodes to PowerPoint objects.

The capability *map* is not the same as native *depth*. Archium currently
implements a shallow slice of the PowerPoint object model (basic text, limited
shapes, pictures, optional chart/table modes, optional structured masters).
Constructs listed in ``POWERPOINT_NATIVE_DEPTH_INVENTORY`` as
``NOT_IMPLEMENTED`` must not be marketed as “深度原生 PowerPoint”.
"""

from __future__ import annotations

from enum import StrEnum
from typing import cast

from pydantic import Field

from archium.domain._base import DomainModel
from archium.domain.visual.render_scene import (
    BaseRenderNode,
    ChartNode,
    ImageNode,
    ShapeNode,
    TableNode,
)


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


class PowerPointDepthStatus(StrEnum):
    """Honest build status for a PowerPoint object-model surface area."""

    IMPLEMENTED = "implemented"
    PARTIAL = "partial"
    NOT_IMPLEMENTED = "not_implemented"


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


class PowerPointDepthEntry(DomainModel):
    """One row on the native-depth map (implemented vs still empty)."""

    id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    status: PowerPointDepthStatus
    pptx_object_hint: str = ""
    notes: str = ""


# Forbidden product/docs phrasing until depth inventory is substantially green.
FORBIDDEN_NATIVE_DEPTH_CLAIMS: tuple[str, ...] = (
    "深度原生 PowerPoint",
    "deep native PowerPoint",
    "PowerPoint-complete",
    "与 PowerPoint 完全等价",
    "完整原生对象模型",
)


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
        limitations=[
            "V1 supports rectangle, ellipse, line, and card only.",
            "No connector, preset geometry library, freeform path, group, "
            "gradient, pattern, glow, or full effect model.",
        ],
        validation_rules=["node_identity_preserved", "geometry_within_tolerance"],
    ),
    "image": PowerPointCapabilityMapping(
        scene_node_type="image",
        pptx_object_type="p:pic",
        fidelity=PowerPointFidelity.NATIVE_STABLE,
        limitations=[
            "Source pixels remain raster even though the picture object is native.",
            "Picture-as-shape crop, soft edges, and complex picture effects are not modeled.",
        ],
        validation_rules=["node_identity_preserved", "asset_resolved"],
    ),
    "drawing": PowerPointCapabilityMapping(
        scene_node_type="drawing",
        pptx_object_type="p:pic",
        fidelity=PowerPointFidelity.NATIVE_STABLE,
        limitations=["V1 preserves the architectural drawing as a picture object."],
        validation_rules=["node_identity_preserved", "asset_resolved", "drawing_crop_policy"],
    ),
    "chart": PowerPointCapabilityMapping(
        scene_node_type="chart",
        pptx_object_type="c:chart (native) or p:sp bake (cross-app)",
        fidelity=PowerPointFidelity.NATIVE_STABLE,
        mapping_cardinality=MappingCardinality.ONE_TO_ONE,
        limitations=[
            "NATIVE_DATA_BACKED emits PowerPoint charts with embedded workbook data.",
            "CROSS_APP_STABLE bakes series as shapes/images (one_to_many emissions).",
            "Chart depth is dual-mode export only — not a full chartEx / style effect surface.",
        ],
        validation_rules=["node_identity_preserved", "chart_series_preserved"],
    ),
    "table": PowerPointCapabilityMapping(
        scene_node_type="table",
        pptx_object_type="a:tbl (native) or p:sp/text grid (cross-app)",
        fidelity=PowerPointFidelity.NATIVE_STABLE,
        mapping_cardinality=MappingCardinality.ONE_TO_ONE,
        limitations=[
            "NATIVE_DATA_BACKED emits editable PowerPoint tables.",
            "CROSS_APP_STABLE renders headers/rows as shape+text grids (one_to_many).",
            "Table styling depth (merged cells, theme table styles) is limited.",
        ],
        validation_rules=["node_identity_preserved", "table_grid_preserved"],
    ),
}


POWERPOINT_NATIVE_DEPTH_INVENTORY: tuple[PowerPointDepthEntry, ...] = (
    PowerPointDepthEntry(
        id="text_body",
        label="Text body",
        status=PowerPointDepthStatus.IMPLEMENTED,
        pptx_object_hint="p:sp + p:txBody",
        notes="Basic editable text frames; advanced typography/effects limited.",
    ),
    PowerPointDepthEntry(
        id="basic_shape",
        label="Basic shape (rect/ellipse/line/card)",
        status=PowerPointDepthStatus.PARTIAL,
        pptx_object_hint="p:sp",
        notes="Card/ellipse/line often normalize toward rectangle in the V1 backend.",
    ),
    PowerPointDepthEntry(
        id="picture",
        label="Picture",
        status=PowerPointDepthStatus.IMPLEMENTED,
        pptx_object_hint="p:pic",
        notes="Raster pictures only.",
    ),
    PowerPointDepthEntry(
        id="native_chart",
        label="Native Chart + embedded workbook",
        status=PowerPointDepthStatus.PARTIAL,
        pptx_object_hint="c:chart + embeddings",
        notes="Opt-in via ChartExportMode.NATIVE_DATA_BACKED when series data exists.",
    ),
    PowerPointDepthEntry(
        id="native_table",
        label="Native Table",
        status=PowerPointDepthStatus.PARTIAL,
        pptx_object_hint="a:tbl",
        notes="Opt-in via ChartExportMode.NATIVE_DATA_BACKED when grid data exists.",
    ),
    PowerPointDepthEntry(
        id="master_layout",
        label="Slide Master / Layout",
        status=PowerPointDepthStatus.PARTIAL,
        pptx_object_hint="p:sldMaster / p:sldLayout",
        notes="STRUCTURED mode emits masters/layouts; FILL_NATIVE in-place preservation incomplete.",
    ),
    PowerPointDepthEntry(
        id="placeholder",
        label="Placeholder inheritance",
        status=PowerPointDepthStatus.PARTIAL,
        pptx_object_hint="p:ph",
        notes="Declared placeholders on structured layouts; not full enterprise template fill.",
    ),
    PowerPointDepthEntry(
        id="speaker_notes",
        label="Speaker Notes",
        status=PowerPointDepthStatus.IMPLEMENTED,
        pptx_object_hint="p:notes",
        notes="Notes text export is supported on the render-plan path.",
    ),
    PowerPointDepthEntry(
        id="connector",
        label="Connector",
        status=PowerPointDepthStatus.NOT_IMPLEMENTED,
        pptx_object_hint="p:cxnSp",
    ),
    PowerPointDepthEntry(
        id="preset_shape",
        label="Preset Shape library",
        status=PowerPointDepthStatus.NOT_IMPLEMENTED,
        pptx_object_hint="prstGeom beyond rect/ellipse/line",
    ),
    PowerPointDepthEntry(
        id="freeform_path",
        label="Freeform Path",
        status=PowerPointDepthStatus.NOT_IMPLEMENTED,
        pptx_object_hint="a:custGeom / path",
    ),
    PowerPointDepthEntry(
        id="group",
        label="Group",
        status=PowerPointDepthStatus.NOT_IMPLEMENTED,
        pptx_object_hint="p:grpSp / GroupNode",
    ),
    PowerPointDepthEntry(
        id="gradient_fill",
        label="Gradient fill",
        status=PowerPointDepthStatus.NOT_IMPLEMENTED,
        pptx_object_hint="a:gradFill",
    ),
    PowerPointDepthEntry(
        id="pattern_fill",
        label="Pattern fill",
        status=PowerPointDepthStatus.NOT_IMPLEMENTED,
        pptx_object_hint="a:pattFill",
    ),
    PowerPointDepthEntry(
        id="shadow_effect",
        label="Shadow effect",
        status=PowerPointDepthStatus.NOT_IMPLEMENTED,
        pptx_object_hint="a:outerShdw",
        notes="ImageNode.shadow is detected then approximated away on PPTX export.",
    ),
    PowerPointDepthEntry(
        id="glow_effect",
        label="Glow effect",
        status=PowerPointDepthStatus.NOT_IMPLEMENTED,
        pptx_object_hint="a:glow",
    ),
    PowerPointDepthEntry(
        id="picture_shape_crop",
        label="Picture / shape crop model",
        status=PowerPointDepthStatus.NOT_IMPLEMENTED,
        pptx_object_hint="a:srcRect / picture as shape",
        notes="Drawing/image fit modes exist; full picture-shape crop OOXML is not claimed.",
    ),
    PowerPointDepthEntry(
        id="transition",
        label="Slide Transition",
        status=PowerPointDepthStatus.NOT_IMPLEMENTED,
        pptx_object_hint="p:transition",
        notes="ENHANCE_NATIVE_DECK route is planned only.",
    ),
)


def capability_for_scene_node(
    node: str | BaseRenderNode,
    *,
    chart_export_mode: str | None = None,
) -> PowerPointCapabilityMapping:
    """Resolve fidelity / cardinality from a node instance, or return the type baseline.

    ``chart_export_mode`` accepts ChartExportMode values as plain strings to avoid
    an import cycle with ``export_fidelity``.
    """
    node_type = node if isinstance(node, str) else node.node_type
    try:
        baseline = RENDER_SCENE_V1_CAPABILITIES[node_type]
    except KeyError as exc:
        raise ValueError(f"No PowerPoint capability mapping for scene node type: {node_type}") from exc
    if isinstance(node, str):
        return baseline

    fidelity = baseline.fidelity
    cardinality = baseline.mapping_cardinality
    pptx_object_type = baseline.pptx_object_type
    limitations = list(baseline.limitations)
    mode = (chart_export_mode or "cross_app_stable").strip().lower()
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
        if node.shadow:
            fidelity = PowerPointFidelity.BAKE_REQUIRED
            limitations.append(
                "Image shadow has no native PPTX effect model in V1; bake or drop required."
            )
        else:
            fidelity = PowerPointFidelity.APPROXIMATE
            limitations.append(
                "V1 PPTX picture export does not preserve corner or border styling."
            )

    if isinstance(node, ChartNode):
        if not node.has_series_data:
            fidelity = PowerPointFidelity.APPROXIMATE
            limitations.append("ChartNode without series data cannot emit a data-backed chart.")
        elif mode == "native_data_backed":
            fidelity = PowerPointFidelity.NATIVE_STABLE
            cardinality = MappingCardinality.ONE_TO_ONE
            pptx_object_type = "c:chart"
        else:
            # CROSS_APP_STABLE shape bake: one node → backdrop + bars + labels.
            fidelity = PowerPointFidelity.BAKE_REQUIRED
            cardinality = MappingCardinality.ONE_TO_MANY
            pptx_object_type = "p:sp"
            limitations.append(
                "CROSS_APP_STABLE chart bake emits multiple p:sp objects (one_to_many)."
            )

    if isinstance(node, TableNode):
        if not node.has_grid_data:
            fidelity = PowerPointFidelity.APPROXIMATE
            limitations.append("TableNode without headers/rows cannot emit a native table.")
        elif mode == "native_data_backed":
            fidelity = PowerPointFidelity.NATIVE_STABLE
            cardinality = MappingCardinality.ONE_TO_ONE
            pptx_object_type = "a:tbl"
        else:
            fidelity = PowerPointFidelity.BAKE_REQUIRED
            cardinality = MappingCardinality.ONE_TO_MANY
            pptx_object_type = "p:sp"
            limitations.append(
                "CROSS_APP_STABLE table bake emits a shape/text grid (one_to_many)."
            )

    return cast(
        PowerPointCapabilityMapping,
        baseline.model_copy(
            update={
                "fidelity": fidelity,
                "mapping_cardinality": cardinality,
                "pptx_object_type": pptx_object_type,
                "limitations": list(dict.fromkeys(limitations)),
            }
        ),
    )


def assess_scene_node(
    node: BaseRenderNode,
    *,
    chart_export_mode: str | None = None,
) -> PowerPointNodeAssessment:
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
    if isinstance(node, ChartNode) and chart_export_mode:
        features.append(f"chart_export_mode:{chart_export_mode}")
    return PowerPointNodeAssessment(
        node_id=node.id,
        node_type=node.node_type,
        mapping=capability_for_scene_node(node, chart_export_mode=chart_export_mode),
        detected_features=features,
    )


def depth_entry(construct_id: str) -> PowerPointDepthEntry:
    for entry in POWERPOINT_NATIVE_DEPTH_INVENTORY:
        if entry.id == construct_id:
            return entry
    raise KeyError(construct_id)


def depth_entries_by_status(
    status: PowerPointDepthStatus,
) -> list[PowerPointDepthEntry]:
    return [entry for entry in POWERPOINT_NATIVE_DEPTH_INVENTORY if entry.status == status]


def native_depth_is_shallow() -> bool:
    """True while most of the PowerPoint object-model map remains unbuilt."""
    not_implemented = depth_entries_by_status(PowerPointDepthStatus.NOT_IMPLEMENTED)
    implemented = depth_entries_by_status(PowerPointDepthStatus.IMPLEMENTED)
    return len(not_implemented) >= len(implemented)


def claim_implies_forbidden_native_depth(text: str) -> bool:
    """Detect marketing phrases that overstate current PowerPoint depth."""
    lowered = text.casefold()
    return any(claim.casefold() in lowered for claim in FORBIDDEN_NATIVE_DEPTH_CLAIMS)
