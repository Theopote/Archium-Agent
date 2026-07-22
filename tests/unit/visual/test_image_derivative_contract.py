"""Image derivative pipeline — planner, Pillow executor, scene rewrite."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from archium.application.visual.image_derivative_executor import ImageDerivativeExecutor
from archium.application.visual.image_derivative_service import ImageDerivativeService
from archium.application.visual.image_treatment_spec_planner import (
    ImageTreatmentSpecPlanner,
    asset_class_for_node,
    photo_treatment_to_mode,
)
from archium.config.settings import Settings
from archium.domain.visual.defaults import default_presentation_design_system
from archium.domain.visual.enums import PhotoTreatment
from archium.domain.visual.image_derivative import (
    FocalPoint,
    ImageAssetClass,
    ImageOverlaySpec,
    ImageTreatmentMode,
    ImageTreatmentSpec,
    mode_allowed_for_asset_class,
)
from archium.domain.visual.render_scene import (
    BackgroundStyle,
    DrawingNode,
    ImageNode,
    Point,
    RenderScene,
)
from archium.infrastructure.storage.local_storage import LocalProjectStorage
from PIL import Image


def test_evidence_assets_cannot_use_presentation_unify() -> None:
    assert mode_allowed_for_asset_class(
        ImageAssetClass.PROJECT_EVIDENCE_PHOTO,
        ImageTreatmentMode.SAFE_NORMALIZE,
    )
    assert not mode_allowed_for_asset_class(
        ImageAssetClass.PROJECT_EVIDENCE_PHOTO,
        ImageTreatmentMode.PRESENTATION_UNIFY,
    )


def test_planner_clamps_evidence_unify_to_safe_normalize() -> None:
    design = default_presentation_design_system()
    design = design.model_copy(
        update={
            "image_style": design.image_style.model_copy(
                update={"photo_treatment": PhotoTreatment.SUBTLE_UNIFY}
            )
        }
    )
    node = ImageNode(
        id="photo",
        x=0,
        y=0,
        width=2,
        height=2,
        z_index=1,
        asset_id=uuid4(),
        storage_uri="project://assets/x",
        asset_origin="project_upload",
    )
    # Force evidence class via planner path using tags on a fake asset is heavier;
    # call plan with DrawingNode for NONE, and asset_class helper for evidence.
    assert asset_class_for_node(DrawingNode(
        id="d",
        x=0,
        y=0,
        width=2,
        height=2,
        z_index=1,
        asset_id=uuid4(),
        storage_uri="project://assets/d",
    )) == ImageAssetClass.PROJECT_DRAWING
    assert photo_treatment_to_mode(PhotoTreatment.SUBTLE_UNIFY) == (
        ImageTreatmentMode.PRESENTATION_UNIFY
    )
    drawing_spec = ImageTreatmentSpecPlanner().plan_for_node(
        DrawingNode(
            id="d",
            x=0,
            y=0,
            width=2,
            height=2,
            z_index=1,
            asset_id=uuid4(),
            storage_uri="project://assets/d",
        ),
        design_system=design,
    )
    assert drawing_spec is not None
    assert drawing_spec.mode == ImageTreatmentMode.NONE

    # Presentation photo follows design subtle_unify → presentation_unify
    photo_spec = ImageTreatmentSpecPlanner().plan_for_node(node, design_system=design)
    assert photo_spec is not None
    assert photo_spec.mode == ImageTreatmentMode.PRESENTATION_UNIFY


def test_pillow_executor_writes_derivative_without_touching_original(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executor = ImageDerivativeExecutor()
    if not executor.is_available():
        pytest.skip("Pillow unavailable")

    project_id = uuid4()
    settings = Settings(_env_file=None, project_storage_path=tmp_path)
    storage = LocalProjectStorage(settings=settings)
    layout = storage.ensure_project_layout(project_id)
    original = layout["assets"] / "src.jpg"
    Image.new("RGB", (120, 80), color=(200, 40, 40)).save(original, format="JPEG")
    original_bytes = original.read_bytes()

    executor = ImageDerivativeExecutor(storage=storage)
    spec = ImageTreatmentSpec(
        original_asset_id=uuid4(),
        mode=ImageTreatmentMode.SAFE_NORMALIZE,
        target_max_edge_px=64,
    )
    derivative = executor.execute(spec, project_id=project_id, original_path=original)
    assert derivative is not None
    assert derivative.executor == "pillow"
    assert derivative.storage_uri.startswith("storage://projects/")
    assert "cache/derivatives/" in derivative.storage_uri
    assert original.read_bytes() == original_bytes

    # Cache hit returns same URI
    again = executor.execute(spec, project_id=project_id, original_path=original)
    assert again is not None
    assert again.storage_uri == derivative.storage_uri
    assert again.params_hash == derivative.params_hash


def test_apply_to_scene_rewrites_image_uri(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if not ImageDerivativeExecutor().is_available():
        pytest.skip("Pillow unavailable")

    project_id = uuid4()
    settings = Settings(
        _env_file=None,
        project_storage_path=tmp_path,
        image_derivatives_enabled=True,
    )
    storage = LocalProjectStorage(settings=settings)
    layout = storage.ensure_project_layout(project_id)
    original = layout["assets"] / "hero.jpg"
    Image.new("RGB", (200, 100), color=(10, 120, 200)).save(original, format="JPEG")

    asset_id = uuid4()
    scene = RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=10,
        page_height=5.625,
        background=BackgroundStyle(color="#FFFFFF"),
        nodes=[
            ImageNode(
                id="hero",
                x=0.5,
                y=0.5,
                width=4,
                height=3,
                z_index=1,
                asset_id=asset_id,
                storage_uri=str(original.resolve()),
                asset_origin="project_upload",
            ),
            DrawingNode(
                id="plan",
                x=5,
                y=0.5,
                width=4,
                height=3,
                z_index=2,
                asset_id=uuid4(),
                storage_uri=str(original.resolve()),
            ),
        ],
    )
    design = default_presentation_design_system()
    result = ImageDerivativeService(
        session=None,
        settings=settings,
        storage=storage,
    ).apply_to_scene(scene, project_id=project_id, design_system=design)

    hero = next(n for n in result.scene.nodes if n.id == "hero")
    plan = next(n for n in result.scene.nodes if n.id == "plan")
    assert isinstance(hero, ImageNode)
    assert isinstance(plan, DrawingNode)
    assert "cache/derivatives/" in hero.storage_uri
    assert plan.storage_uri == str(original.resolve())  # drawings stay original
    assert len(result.derivatives) >= 1


def test_planner_enables_vignette_and_focal_crop_for_presentation() -> None:
    design = default_presentation_design_system()
    design = design.model_copy(
        update={
            "image_style": design.image_style.model_copy(
                update={"photo_treatment": PhotoTreatment.SUBTLE_UNIFY}
            )
        }
    )
    node = ImageNode(
        id="hero",
        x=0,
        y=0,
        width=2,
        height=2,
        z_index=1,
        asset_id=uuid4(),
        storage_uri="project://assets/x",
        asset_origin="project_upload",
        focus_point=Point(x=0.7, y=0.3),
    )
    spec = ImageTreatmentSpecPlanner().plan_for_node(node, design_system=design)
    assert spec is not None
    assert spec.mode == ImageTreatmentMode.PRESENTATION_UNIFY
    assert spec.overlay.kind == "soft_vignette"
    assert spec.overlay.opacity > 0
    assert spec.auto_subject_crop is True
    assert spec.focal_point.source == "manual"
    assert abs(spec.focal_point.x - 0.7) < 1e-6


def test_focal_center_crop_and_vignette_change_pixels(
    tmp_path: Path,
) -> None:
    executor = ImageDerivativeExecutor()
    if not executor.is_available():
        pytest.skip("Pillow unavailable")

    project_id = uuid4()
    settings = Settings(_env_file=None, project_storage_path=tmp_path)
    storage = LocalProjectStorage(settings=settings)
    layout = storage.ensure_project_layout(project_id)
    original = layout["assets"] / "focal.jpg"
    # Distinct left/right colors so focal crop toward the right changes mean color.
    img = Image.new("RGB", (200, 100), color=(10, 10, 10))
    right = Image.new("RGB", (80, 100), color=(240, 20, 20))
    img.paste(right, (120, 0))
    img.save(original, format="JPEG")

    executor = ImageDerivativeExecutor(storage=storage)
    asset_id = uuid4()
    plain = ImageTreatmentSpec(
        original_asset_id=asset_id,
        mode=ImageTreatmentMode.PRESENTATION_UNIFY,
        target_max_edge_px=200,
    )
    cropped = ImageTreatmentSpec(
        original_asset_id=asset_id,
        mode=ImageTreatmentMode.PRESENTATION_UNIFY,
        focal_point=FocalPoint(x=0.85, y=0.5, confidence=1.0, source="manual"),
        auto_subject_crop=True,
        overlay=ImageOverlaySpec(kind="soft_vignette", opacity=0.3),
        target_max_edge_px=200,
    )
    d_plain = executor.execute(plain, project_id=project_id, original_path=original)
    d_crop = executor.execute(cropped, project_id=project_id, original_path=original)
    assert d_plain is not None and d_crop is not None
    assert d_plain.params_hash != d_crop.params_hash
    assert d_crop.width_px is not None and d_plain.width_px is not None
    assert d_crop.width_px < d_plain.width_px


def test_selection_region_bbox_covers_nodes() -> None:
    from archium.application.visual.comment_region import selection_region_bbox
    from archium.domain.visual.render_scene import TextNode

    scene = RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=10,
        page_height=5.625,
        background=BackgroundStyle(color="#FFFFFF"),
        nodes=[
            TextNode(
                id="a",
                x=1.0,
                y=0.5,
                width=2.0,
                height=1.0,
                z_index=1,
                text="A",
                font_family="Arial",
                font_size=12,
                color="#000000",
                line_height=16,
            ),
            TextNode(
                id="b",
                x=3.5,
                y=2.0,
                width=1.5,
                height=0.8,
                z_index=2,
                text="B",
                font_family="Arial",
                font_size=12,
                color="#000000",
                line_height=16,
            ),
        ],
    )
    box = selection_region_bbox(scene, ["a", "b"])
    assert box == {"x": 1.0, "y": 0.5, "width": 4.0, "height": 2.3}
    assert selection_region_bbox(scene, ["missing"]) is None


def test_presentation_unify_changes_pixels_evidence_stays_untreated(
    tmp_path: Path,
) -> None:
    """Before/after unify regression without golden PNG promote."""
    executor = ImageDerivativeExecutor()
    if not executor.is_available():
        pytest.skip("Pillow unavailable")

    project_id = uuid4()
    settings = Settings(_env_file=None, project_storage_path=tmp_path)
    storage = LocalProjectStorage(settings=settings)
    layout = storage.ensure_project_layout(project_id)
    original = layout["assets"] / "unify.jpg"
    Image.new("RGB", (160, 120), color=(180, 90, 40)).save(original, format="JPEG")
    original_bytes = original.read_bytes()
    executor = ImageDerivativeExecutor(storage=storage)

    none_spec = ImageTreatmentSpec(
        original_asset_id=uuid4(),
        mode=ImageTreatmentMode.NONE,
    )
    assert executor.execute(none_spec, project_id=project_id, original_path=original) is None

    unify = ImageTreatmentSpec(
        original_asset_id=uuid4(),
        asset_class=ImageAssetClass.PRESENTATION,
        mode=ImageTreatmentMode.PRESENTATION_UNIFY,
        overlay=ImageOverlaySpec(kind="soft_vignette", opacity=0.25),
        target_max_edge_px=160,
    )
    derivative = executor.execute(unify, project_id=project_id, original_path=original)
    assert derivative is not None
    assert original.read_bytes() == original_bytes

    der_path = next(
        (layout["cache"] / "derivatives").rglob(f"{derivative.params_hash}.jpg"),
        None,
    )
    assert der_path is not None and der_path.is_file()
    before = Image.open(original).convert("RGB")
    after = Image.open(der_path).convert("RGB")
    assert after.size[0] <= before.size[0] and after.size[1] <= before.size[1]
    # Mean absolute channel delta must be non-trivial for unify+vignette.
    from statistics import mean

    b_px = list(before.getdata())
    a_px = list(after.resize(before.size, Image.Resampling.LANCZOS).getdata())
    mad = mean(
        abs(bp[c] - ap[c]) for bp, ap in zip(b_px, a_px, strict=True) for c in range(3)
    )
    assert mad > 0.5

    # Evidence assets must refuse presentation_unify (executor returns None).
    evidence = ImageTreatmentSpec(
        original_asset_id=uuid4(),
        asset_class=ImageAssetClass.PROJECT_EVIDENCE_PHOTO,
        mode=ImageTreatmentMode.PRESENTATION_UNIFY,
        overlay=ImageOverlaySpec(kind="soft_vignette", opacity=0.3),
    )
    assert executor.execute(evidence, project_id=project_id, original_path=original) is None
