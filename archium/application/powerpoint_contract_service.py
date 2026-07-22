"""Validation services for PPTX capability disclosure and scene closure."""

from __future__ import annotations

from pydantic import Field

from archium.domain._base import DomainModel
from archium.domain.powerpoint_capability import (
    PowerPointCapabilityMapping,
    capability_for_scene_node,
)
from archium.domain.visual.render_scene import RenderScene


class RendererEmission(DomainModel):
    """One visible object emitted by a renderer, traced to its authored node."""

    scene_node_id: str = Field(min_length=1)
    pptx_object_type: str = Field(min_length=1)


class SceneClosureReport(DomainModel):
    valid: bool
    missing_node_ids: list[str] = Field(default_factory=list)
    unexpected_node_ids: list[str] = Field(default_factory=list)
    duplicate_node_ids: list[str] = Field(default_factory=list)


class PowerPointContractService:
    """Fail-closed checks at the RenderScene -> renderer boundary."""

    def capabilities(self, scene: RenderScene) -> list[PowerPointCapabilityMapping]:
        return [capability_for_scene_node(node.node_type) for node in scene.sorted_nodes()]

    def validate_scene_closure(
        self, scene: RenderScene, emissions: list[RendererEmission]
    ) -> SceneClosureReport:
        expected = {node.id for node in scene.nodes if node.visible}
        emitted_ids = [item.scene_node_id for item in emissions]
        emitted = set(emitted_ids)
        duplicates = sorted({node_id for node_id in emitted if emitted_ids.count(node_id) > 1})
        missing = sorted(expected - emitted)
        unexpected = sorted(emitted - expected)
        return SceneClosureReport(
            valid=not missing and not unexpected and not duplicates,
            missing_node_ids=missing,
            unexpected_node_ids=unexpected,
            duplicate_node_ids=duplicates,
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
                f"duplicates={report.duplicate_node_ids}"
            )

