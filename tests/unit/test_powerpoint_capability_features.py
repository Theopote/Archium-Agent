from archium.domain.powerpoint_capability import PowerPointFidelity, assess_scene_node
from archium.domain.visual.render_scene import ImageNode, ShadowStyle, ShapeNode


def test_simple_rectangle_is_native_stable() -> None:
    node = ShapeNode(id="rect", x=0, y=0, width=2, height=1, shape_kind="rectangle")
    assessment = assess_scene_node(node)
    assert assessment.mapping.fidelity == PowerPointFidelity.NATIVE_STABLE
    assert "shape_kind:rectangle" in assessment.detected_features


def test_non_rectangle_shape_discloses_backend_normalization() -> None:
    node = ShapeNode(id="ellipse", x=0, y=0, width=2, height=1, shape_kind="ellipse")
    assessment = assess_scene_node(node)
    assert assessment.mapping.fidelity == PowerPointFidelity.APPROXIMATE
    assert any("normalizes ellipse geometry" in item for item in assessment.mapping.limitations)


def test_unpreserved_picture_effects_are_bake_required() -> None:
    node = ImageNode(
        id="photo",
        x=0,
        y=0,
        width=2,
        height=1,
        storage_uri="asset://photo.png",
        shadow=ShadowStyle(),
    )
    assessment = assess_scene_node(node)
    # ImageNode.shadow has no native PPTX effect model in V1 — bake or drop.
    assert assessment.mapping.fidelity == PowerPointFidelity.BAKE_REQUIRED
    assert "shadow" in assessment.detected_features


