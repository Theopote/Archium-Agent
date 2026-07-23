from uuid import uuid4

from archium.application.powerpoint_contract_service import (
    PowerPointContractService,
    RendererEmission,
)
from archium.domain.powerpoint_capability import (
    MappingCardinality,
    PowerPointCapabilityMapping,
    PowerPointFidelity,
)
from archium.domain.visual.render_scene import BackgroundStyle, RenderScene, ShapeNode


def _scene() -> RenderScene:
    return RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=13.333,
        page_height=7.5,
        background=BackgroundStyle(color="#ffffff"),
        nodes=[ShapeNode(id="icon", x=1, y=1, width=1, height=1)],
    )


def _emission(emission_id: str, sequence: int) -> RendererEmission:
    return RendererEmission(
        emission_id=emission_id,
        source_scene_node_id="icon",
        pptx_object_type="p:sp",
        role="vector_part",
        sequence=sequence,
    )


def test_one_to_many_contract_allows_multiple_traceable_objects() -> None:
    mapping = PowerPointCapabilityMapping(
        scene_node_type="shape",
        pptx_object_type="p:grpSp / p:sp",
        fidelity=PowerPointFidelity.NATIVE_NORMALIZED,
        mapping_cardinality=MappingCardinality.ONE_TO_MANY,
    )
    report = PowerPointContractService().validate_scene_closure(
        _scene(),
        [_emission("icon-part-1", 0), _emission("icon-part-2", 1)],
        capability_overrides={"icon": mapping},
    )
    assert report.valid


def test_plan_emissions_expands_cross_app_chart_bake_as_one_to_many() -> None:
    from archium.domain.visual.render_scene import ChartNode, ChartSeriesData

    scene = RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=10,
        page_height=5.625,
        background=BackgroundStyle(color="#ffffff"),
        nodes=[
            ChartNode(
                id="chart1",
                x=1,
                y=1,
                width=4,
                height=3,
                series=[
                    ChartSeriesData(
                        name="Series",
                        labels=["A", "B"],
                        values=[10.0, 20.0],
                    )
                ],
            )
        ],
    )
    contracts = PowerPointContractService()
    emissions = contracts.plan_emissions(scene, chart_export_mode="cross_app_stable")
    # backdrop + 2 bars + 2 labels
    assert len(emissions) == 5
    roles = [item.role for item in emissions]
    assert roles.count("chart_bar") == 2
    assert roles.count("chart_label") == 2
    contracts.require_scene_closure(
        scene, emissions, chart_export_mode="cross_app_stable"
    )


def test_plan_emissions_native_chart_stays_one_to_one() -> None:
    from archium.domain.visual.render_scene import ChartNode, ChartSeriesData

    scene = RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=10,
        page_height=5.625,
        background=BackgroundStyle(color="#ffffff"),
        nodes=[
            ChartNode(
                id="chart1",
                x=1,
                y=1,
                width=4,
                height=3,
                series=[
                    ChartSeriesData(name="Series", labels=["A"], values=[1.0])
                ],
            )
        ],
    )
    contracts = PowerPointContractService()
    emissions = contracts.plan_emissions(scene, chart_export_mode="native_data_backed")
    assert len(emissions) == 1
    assert emissions[0].pptx_object_type == "c:chart"
    contracts.require_scene_closure(
        scene, emissions, chart_export_mode="native_data_backed"
    )


def test_one_to_one_contract_rejects_multiple_objects() -> None:
    report = PowerPointContractService().validate_scene_closure(
        _scene(),
        [_emission("icon-part-1", 0), _emission("icon-part-2", 1)],
    )
    assert not report.valid
    assert report.cardinality_violations == [
        "icon:one_to_one expected 1 emission, found 2"
    ]


def test_duplicate_emission_identity_is_always_invalid() -> None:
    mapping = PowerPointCapabilityMapping(
        scene_node_type="shape",
        pptx_object_type="p:grpSp / p:sp",
        fidelity=PowerPointFidelity.NATIVE_NORMALIZED,
        mapping_cardinality=MappingCardinality.ONE_TO_MANY,
    )
    report = PowerPointContractService().validate_scene_closure(
        _scene(),
        [_emission("same-id", 0), _emission("same-id", 1)],
        capability_overrides={"icon": mapping},
    )
    assert not report.valid
    assert report.duplicate_emission_ids == ["same-id"]


def test_one_to_many_requires_unique_sequence_values() -> None:
    mapping = PowerPointCapabilityMapping(
        scene_node_type="shape",
        pptx_object_type="p:grpSp / p:sp",
        fidelity=PowerPointFidelity.NATIVE_NORMALIZED,
        mapping_cardinality=MappingCardinality.ONE_TO_MANY,
    )
    report = PowerPointContractService().validate_scene_closure(
        _scene(),
        [_emission("icon-part-1", 0), _emission("icon-part-2", 0)],
        capability_overrides={"icon": mapping},
    )
    assert not report.valid
    assert "duplicate sequence" in report.cardinality_violations[0]


def test_many_to_one_accepts_multi_source_emission() -> None:
    scene = RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=13.333,
        page_height=7.5,
        background=BackgroundStyle(color="#ffffff"),
        nodes=[
            ShapeNode(id="a", x=1, y=1, width=1, height=1),
            ShapeNode(id="b", x=2, y=1, width=1, height=1),
        ],
    )
    many = PowerPointCapabilityMapping(
        scene_node_type="shape",
        pptx_object_type="p:sp",
        fidelity=PowerPointFidelity.NATIVE_NORMALIZED,
        mapping_cardinality=MappingCardinality.MANY_TO_ONE,
    )
    emission = RendererEmission(
        emission_id="merged",
        source_scene_node_id="a",
        additional_source_node_ids=["b"],
        pptx_object_type="p:sp",
        role="merged",
        sequence=0,
    )
    report = PowerPointContractService().validate_scene_closure(
        scene,
        [emission],
        capability_overrides={"a": many, "b": many},
    )
    assert report.valid


def test_many_to_one_rejects_single_source_schema() -> None:
    mapping = PowerPointCapabilityMapping(
        scene_node_type="shape",
        pptx_object_type="p:sp",
        fidelity=PowerPointFidelity.NATIVE_NORMALIZED,
        mapping_cardinality=MappingCardinality.MANY_TO_ONE,
    )
    report = PowerPointContractService().validate_scene_closure(
        _scene(),
        [_emission("only", 0)],
        capability_overrides={"icon": mapping},
    )
    assert not report.valid
    assert any("multi-source" in item for item in report.cardinality_violations)

