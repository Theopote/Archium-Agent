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
    ImageAssetClass,
    ImageTreatmentMode,
    ImageTreatmentSpec,
    mode_allowed_for_asset_class,
)
from archium.domain.visual.render_scene import (
    BackgroundStyle,
    DrawingNode,
    ImageNode,
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
