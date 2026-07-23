"""Tests for visual workflow RenderScene repair integration."""

from __future__ import annotations

from pathlib import Path

from archium.application.visual.visual_scene_repair_workflow_service import (
    VisualSceneRepairWorkflowService,
)
from archium.config.settings import Settings
from archium.domain.visual.defaults import default_presentation_design_system
from tests.unit.visual.test_studio_scene_service import _seed_slide_with_plan


def test_repair_and_persist_writes_scene_json(db_session, tmp_path: Path) -> None:
    presentation, slide, plan = _seed_slide_with_plan(db_session)
    settings = Settings(
        _env_file=None,
        database_path=tmp_path / "db.sqlite",
        output_path=tmp_path / "outputs",
        project_storage_path=tmp_path / "projects",
        chroma_path=tmp_path / "chroma",
        workflow_checkpoint_path=tmp_path / "checkpoints.db",
    )
    service = VisualSceneRepairWorkflowService(db_session, settings=settings)
    result = service.repair_and_persist(
        presentation_id=presentation.id,
        project_id=presentation.project_id,
        slides=[slide],
        plans=[plan],
        design_system=default_presentation_design_system(),
        output_dir=tmp_path / "visual_out",
        max_rounds=2,
        export_scene_pptx=False,
    )
    assert len(result.scenes) == 1
    assert result.scene_paths
    scene_path = Path(result.scene_paths[0])
    assert scene_path.is_file()
    assert scene_path.name == "render_scene.json"


def test_compile_scenes_from_layout_plans(db_session) -> None:
    presentation, slide, plan = _seed_slide_with_plan(db_session)
    service = VisualSceneRepairWorkflowService(db_session)
    scenes = service.compile_scenes(
        slides=[slide],
        plans=[plan],
        design_system=default_presentation_design_system(),
        presentation_id=presentation.id,
        project_id=presentation.project_id,
    )
    assert len(scenes) == 1
    assert scenes[0].slide_id == slide.id


def test_repair_and_persist_reuses_scene_id_by_layout_plan(
    db_session, tmp_path: Path
) -> None:
    presentation, slide, plan = _seed_slide_with_plan(db_session)
    settings = Settings(
        _env_file=None,
        database_path=tmp_path / "db.sqlite",
        output_path=tmp_path / "outputs",
        project_storage_path=tmp_path / "projects",
        chroma_path=tmp_path / "chroma",
        workflow_checkpoint_path=tmp_path / "checkpoints.db",
    )
    service = VisualSceneRepairWorkflowService(db_session, settings=settings)
    kwargs = dict(
        presentation_id=presentation.id,
        project_id=presentation.project_id,
        slides=[slide],
        plans=[plan],
        design_system=default_presentation_design_system(),
        output_dir=tmp_path / "visual_out",
        max_rounds=1,
        export_scene_pptx=False,
    )
    first = service.repair_and_persist(**kwargs)
    second = service.repair_and_persist(**kwargs)
    assert first.scenes and second.scenes
    assert first.scenes[0].id == second.scenes[0].id
    assert second.scenes[0].version >= first.scenes[0].version
