"""Validation services for PPTX capability disclosure and scene closure."""

from __future__ import annotations

from pydantic import Field, model_validator

from archium.domain._base import DomainModel
from archium.domain.powerpoint_capability import (
    MappingCardinality,
    PowerPointCapabilityMapping,
    PowerPointFidelity,
    PowerPointNodeAssessment,
    assess_scene_node,
    capability_for_scene_node,
)
from archium.domain.visual.render_scene import ChartNode, RenderScene, TableNode


class RendererEmission(DomainModel):
    """One visible object emitted by a renderer, traced to authored node(s)."""

    emission_id: str = Field(min_length=1)
    source_scene_node_id: str = Field(min_length=1)
    pptx_object_type: str = Field(min_length=1)
    role: str = Field(default="primary", min_length=1)
    sequence: int = Field(default=0, ge=0)
    additional_source_node_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _normalize_additional_sources(self) -> RendererEmission:
        extras = [
            node_id.strip()
            for node_id in self.additional_source_node_ids
            if node_id.strip() and node_id.strip() != self.source_scene_node_id
        ]
        object.__setattr__(self, "additional_source_node_ids", list(dict.fromkeys(extras)))
        return self

    @property
    def all_source_node_ids(self) -> list[str]:
        return [self.source_scene_node_id, *self.additional_source_node_ids]

    @property
    def is_multi_source(self) -> bool:
        return len(self.all_source_node_ids) > 1


class SceneClosureReport(DomainModel):
    valid: bool
    missing_node_ids: list[str] = Field(default_factory=list)
    unexpected_node_ids: list[str] = Field(default_factory=list)
    duplicate_emission_ids: list[str] = Field(default_factory=list)
    cardinality_violations: list[str] = Field(default_factory=list)


class CapabilityExportGateReport(DomainModel):
    """Pre-export capability gate: unsupported / bake-required findings."""

    valid: bool
    unsupported_node_ids: list[str] = Field(default_factory=list)
    bake_required_node_ids: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class EmissionObjectTypeReport(DomainModel):
    """Post-plan emission object-type check against capability mappings."""

    valid: bool
    mismatches: list[str] = Field(default_factory=list)


class PowerPointContractService:
    """Fail-closed checks at the RenderScene -> renderer boundary."""

    def capabilities(
        self,
        scene: RenderScene,
        *,
        chart_export_mode: str | None = None,
    ) -> list[PowerPointCapabilityMapping]:
        return [
            capability_for_scene_node(node, chart_export_mode=chart_export_mode)
            for node in scene.sorted_nodes()
            if node.visible
        ]

    def assessments(
        self,
        scene: RenderScene,
        *,
        chart_export_mode: str | None = None,
    ) -> list[PowerPointNodeAssessment]:
        return [
            assess_scene_node(node, chart_export_mode=chart_export_mode)
            for node in scene.sorted_nodes()
            if node.visible
        ]

    def plan_emissions(
        self,
        scene: RenderScene,
        *,
        chart_export_mode: str | None = None,
    ) -> list[RendererEmission]:
        """Plan traceable emissions, including one_to_many bake expansions."""
        emissions: list[RendererEmission] = []
        for node in scene.sorted_nodes():
            if not node.visible:
                continue
            mapping = capability_for_scene_node(node, chart_export_mode=chart_export_mode)
            if mapping.mapping_cardinality == MappingCardinality.ONE_TO_MANY:
                emissions.extend(self._plan_one_to_many(node, mapping))
            else:
                emissions.append(
                    RendererEmission(
                        emission_id=f"{node.id}:0",
                        source_scene_node_id=node.id,
                        pptx_object_type=mapping.pptx_object_type,
                        role="primary",
                        sequence=0,
                    )
                )
        return emissions

    def _plan_one_to_many(
        self,
        node: object,
        mapping: PowerPointCapabilityMapping,
    ) -> list[RendererEmission]:
        """Expand a single scene node into multiple planned PPTX objects."""
        if isinstance(node, ChartNode) and node.has_series_data:
            primary = next((series for series in node.series if series.values), node.series[0])
            value_count = max(1, len(primary.values))
            planned: list[RendererEmission] = [
                RendererEmission(
                    emission_id=f"{node.id}:0",
                    source_scene_node_id=node.id,
                    pptx_object_type="p:sp",
                    role="chart_backdrop",
                    sequence=0,
                )
            ]
            sequence = 1
            for index in range(value_count):
                planned.append(
                    RendererEmission(
                        emission_id=f"{node.id}:{sequence}",
                        source_scene_node_id=node.id,
                        pptx_object_type="p:sp",
                        role="chart_bar",
                        sequence=sequence,
                    )
                )
                sequence += 1
                planned.append(
                    RendererEmission(
                        emission_id=f"{node.id}:{sequence}",
                        source_scene_node_id=node.id,
                        pptx_object_type="p:sp + p:txBody",
                        role="chart_label",
                        sequence=sequence,
                    )
                )
                sequence += 1
            return planned

        if isinstance(node, TableNode) and node.has_grid_data:
            planned: list[RendererEmission] = []
            sequence = 0
            for _header in node.headers:
                planned.append(
                    RendererEmission(
                        emission_id=f"{node.id}:{sequence}",
                        source_scene_node_id=node.id,
                        pptx_object_type="p:sp + p:txBody",
                        role="table_header",
                        sequence=sequence,
                    )
                )
                sequence += 1
            for row in node.rows:
                for _cell in row:
                    planned.append(
                        RendererEmission(
                            emission_id=f"{node.id}:{sequence}",
                            source_scene_node_id=node.id,
                            pptx_object_type="p:sp + p:txBody",
                            role="table_cell",
                            sequence=sequence,
                        )
                    )
                    sequence += 1
            return planned

        # Generic one_to_many fallback: still at least one primary emission.
        return [
            RendererEmission(
                emission_id=f"{getattr(node, 'id', 'node')}:0",
                source_scene_node_id=str(getattr(node, "id", "node")),
                pptx_object_type=mapping.pptx_object_type,
                role="primary",
                sequence=0,
            )
        ]

    def validate_capability_export_gate(
        self,
        scene: RenderScene,
        *,
        chart_export_mode: str | None = None,
    ) -> CapabilityExportGateReport:
        """Pre-export: map nodes → capability and flag unsupported / bake-required."""
        unsupported: list[str] = []
        bake_required: list[str] = []
        limitations: list[str] = []
        for node in scene.sorted_nodes():
            if not node.visible:
                continue
            assessment = assess_scene_node(node, chart_export_mode=chart_export_mode)
            limitations.extend(assessment.mapping.limitations)
            if assessment.mapping.fidelity == PowerPointFidelity.UNSUPPORTED:
                unsupported.append(node.id)
            elif assessment.mapping.fidelity == PowerPointFidelity.BAKE_REQUIRED:
                bake_required.append(node.id)
        return CapabilityExportGateReport(
            valid=not unsupported,
            unsupported_node_ids=unsupported,
            bake_required_node_ids=bake_required,
            limitations=list(dict.fromkeys(limitations)),
        )

    def require_capability_export_gate(
        self,
        scene: RenderScene,
        *,
        chart_export_mode: str | None = None,
    ) -> CapabilityExportGateReport:
        report = self.validate_capability_export_gate(
            scene, chart_export_mode=chart_export_mode
        )
        if not report.valid:
            raise ValueError(
                "Capability export gate failed: unsupported nodes="
                f"{report.unsupported_node_ids}"
            )
        return report

    def validate_emission_object_types(
        self,
        scene: RenderScene,
        emissions: list[RendererEmission],
        *,
        capability_overrides: dict[str, PowerPointCapabilityMapping] | None = None,
        chart_export_mode: str | None = None,
    ) -> EmissionObjectTypeReport:
        """Post-plan: every emission's pptx_object_type must match the mapping."""
        visible = {node.id: node for node in scene.nodes if node.visible}
        overrides = capability_overrides or {}
        mismatches: list[str] = []
        for emission in emissions:
            primary = emission.source_scene_node_id
            if primary not in visible:
                continue
            mapping = overrides.get(primary) or capability_for_scene_node(
                visible[primary], chart_export_mode=chart_export_mode
            )
            expected = mapping.pptx_object_type
            if emission.pptx_object_type != expected and expected not in emission.pptx_object_type:
                # Allow emission type that is a specialization listed in mapping.
                if emission.pptx_object_type not in expected:
                    mismatches.append(
                        f"{emission.emission_id}: got {emission.pptx_object_type!r}, "
                        f"expected {expected!r}"
                    )
        return EmissionObjectTypeReport(valid=not mismatches, mismatches=mismatches)

    def require_emission_object_types(
        self,
        scene: RenderScene,
        emissions: list[RendererEmission],
        *,
        capability_overrides: dict[str, PowerPointCapabilityMapping] | None = None,
        chart_export_mode: str | None = None,
    ) -> None:
        report = self.validate_emission_object_types(
            scene,
            emissions,
            capability_overrides=capability_overrides,
            chart_export_mode=chart_export_mode,
        )
        if not report.valid:
            raise ValueError(
                "Emission object-type validation failed: " + "; ".join(report.mismatches)
            )

    def validate_scene_closure(
        self,
        scene: RenderScene,
        emissions: list[RendererEmission],
        *,
        capability_overrides: dict[str, PowerPointCapabilityMapping] | None = None,
        chart_export_mode: str | None = None,
    ) -> SceneClosureReport:
        visible_nodes = {node.id: node for node in scene.nodes if node.visible}
        expected = set(visible_nodes)
        covered: set[str] = set()
        for item in emissions:
            covered.update(item.all_source_node_ids)
        emission_ids = [item.emission_id for item in emissions]
        duplicate_emissions = sorted(
            {emission_id for emission_id in emission_ids if emission_ids.count(emission_id) > 1}
        )
        missing = sorted(expected - covered)
        unexpected = sorted(covered - expected)
        overrides = capability_overrides or {}
        cardinality_violations: list[str] = []

        for emission in emissions:
            if not emission.is_multi_source:
                continue
            for source_id in emission.all_source_node_ids:
                node = visible_nodes.get(source_id)
                if node is None:
                    continue
                mapping = overrides.get(source_id) or capability_for_scene_node(
                    node, chart_export_mode=chart_export_mode
                )
                if mapping.mapping_cardinality != MappingCardinality.MANY_TO_ONE:
                    cardinality_violations.append(
                        f"{emission.emission_id}: multi-source emission requires "
                        f"many_to_one on {source_id}"
                    )

        for node_id, node in visible_nodes.items():
            matched = [
                item for item in emissions if node_id in item.all_source_node_ids
            ]
            mapping = overrides.get(node_id) or capability_for_scene_node(
                node, chart_export_mode=chart_export_mode
            )
            cardinality = mapping.mapping_cardinality

            if cardinality == MappingCardinality.ONE_TO_ONE:
                if len(matched) != 1:
                    cardinality_violations.append(
                        f"{node_id}:one_to_one expected 1 emission, found {len(matched)}"
                    )
                elif matched[0].is_multi_source:
                    cardinality_violations.append(
                        f"{node_id}:one_to_one cannot share a multi-source emission"
                    )
            elif cardinality == MappingCardinality.ONE_TO_MANY:
                # Multiple PPTX objects from one node are valid — not a duplicate error.
                if not matched:
                    cardinality_violations.append(
                        f"{node_id}:one_to_many expected ≥1 emission, found 0"
                    )
                elif any(item.is_multi_source for item in matched):
                    cardinality_violations.append(
                        f"{node_id}:one_to_many emissions must be single-source"
                    )
                else:
                    sequences = [item.sequence for item in matched]
                    if len(sequences) != len(set(sequences)):
                        cardinality_violations.append(
                            f"{node_id}:one_to_many contains duplicate sequence values"
                        )
            elif cardinality == MappingCardinality.MANY_TO_ONE:
                if len(matched) != 1:
                    cardinality_violations.append(
                        f"{node_id}:many_to_one expected 1 shared emission, found {len(matched)}"
                    )
                elif not matched[0].is_multi_source:
                    cardinality_violations.append(
                        f"{node_id}:many_to_one requires multi-source emission schema "
                        "(additional_source_node_ids)"
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
        self,
        scene: RenderScene,
        emissions: list[RendererEmission],
        *,
        capability_overrides: dict[str, PowerPointCapabilityMapping] | None = None,
        chart_export_mode: str | None = None,
    ) -> None:
        report = self.validate_scene_closure(
            scene,
            emissions,
            capability_overrides=capability_overrides,
            chart_export_mode=chart_export_mode,
        )
        if not report.valid:
            raise ValueError(
                "RenderScene closure violation: "
                f"missing={report.missing_node_ids}, "
                f"unexpected={report.unexpected_node_ids}, "
                f"duplicate_emissions={report.duplicate_emission_ids}, "
                f"cardinality={report.cardinality_violations}"
            )
