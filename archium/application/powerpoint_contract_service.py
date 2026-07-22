"""Validation services for PPTX capability disclosure and scene closure."""

from __future__ import annotations

from pydantic import Field

from archium.domain._base import DomainModel
from archium.domain.powerpoint_capability import (
    MappingCardinality,
    PowerPointCapabilityMapping,
    PowerPointNodeAssessment,
    assess_scene_node,
    capability_for_scene_node,
)
from archium.domain.visual.render_scene import RenderScene


class RendererEmission(DomainModel):
    """One visible object emitted by a renderer, traced to its authored node."""

    emission_id: str = Field(min_length=1)
    source_scene_node_id: str = Field(min_length=1)
    pptx_object_type: str = Field(min_length=1)
    role: str = Field(default="primary", min_length=1)
    sequence: int = Field(default=0, ge=0)


class SceneClosureReport(DomainModel):
    valid: bool
    missing_node_ids: list[str] = Field(default_factory=list)
    unexpected_node_ids: list[str] = Field(default_factory=list)
    duplicate_emission_ids: list[str] = Field(default_factory=list)
    cardinality_violations: list[str] = Field(default_factory=list)


class PowerPointContractService:
    """Fail-closed checks at the RenderScene -> renderer boundary."""

    def capabilities(self, scene: RenderScene) -> list[PowerPointCapabilityMapping]:
        return [capability_for_scene_node(node) for node in scene.sorted_nodes() if node.visible]

    def assessments(self, scene: RenderScene) -> list[PowerPointNodeAssessment]:
        return [assess_scene_node(node) for node in scene.sorted_nodes() if node.visible]

    def validate_scene_closure(
        self,
        scene: RenderScene,
        emissions: list[RendererEmission],
        *,
        capability_overrides: dict[str, PowerPointCapabilityMapping] | None = None,
    ) -> SceneClosureReport:
        visible_nodes = {node.id: node for node in scene.nodes if node.visible}
        expected = set(visible_nodes)
        source_ids = [item.source_scene_node_id for item in emissions]
        emitted_sources = set(source_ids)
        emission_ids = [item.emission_id for item in emissions]
        duplicate_emissions = sorted(
            {emission_id for emission_id in emission_ids if emission_ids.count(emission_id) > 1}
        )
        missing = sorted(expected - emitted_sources)
        unexpected = sorted(emitted_sources - expected)
        overrides = capability_overrides or {}
        cardinality_violations: list[str] = []
        for node_id, node in visible_nodes.items():
            matched = [item for item in emissions if item.source_scene_node_id == node_id]
            mapping = overrides.get(node_id) or capability_for_scene_node(node)
            if mapping.mapping_cardinality == MappingCardinality.ONE_TO_ONE and len(matched) != 1:
                cardinality_violations.append(
                    f"{node_id}:one_to_one expected 1 emission, found {len(matched)}"
                )
            elif mapping.mapping_cardinality == MappingCardinality.ONE_TO_MANY and matched:
                sequences = [item.sequence for item in matched]
                if len(sequences) != len(set(sequences)):
                    cardinality_violations.append(
                        f"{node_id}:one_to_many contains duplicate sequence values"
                    )
            elif mapping.mapping_cardinality == MappingCardinality.MANY_TO_ONE:
                cardinality_violations.append(
                    f"{node_id}:many_to_one requires multi-source emission schema"
                )
        return SceneClosureReport(
            valid=(
                not missing
                and not unexpected
                and not duplicate_emissions
                and not cardinality_violations
            ),
            missing_node_ids=missing,
            unexpected_node_ids=unexpected,
            duplicate_emission_ids=duplicate_emissions,
            cardinality_violations=cardinality_violations,
        )

    def require_scene_closure(
        self, scene: RenderScene, emissions: list[RendererEmission]
    ) -> None:
        report = self.validate_scene_closure(scene, emissions)
        if not report.valid:
            raise ValueError(
                "RenderScene closure violation: "
                f"missing={report.missing_node_ids}, "
                f"unexpected={report.unexpected_node_ids}, "
                f"duplicate_emissions={report.duplicate_emission_ids}, "
                f"cardinality={report.cardinality_violations}"
            )
