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

