"""Tests for SlideRecoveryDeliveryService."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from archium.application.slide_recovery_delivery_service import SlideRecoveryDeliveryService
from archium.config.settings import Settings
from archium.domain.export_fidelity import ExportFidelityLevel
from archium.domain.presentation import Presentation
from archium.domain.project import Project
from archium.domain.slide_recovery import (
    HybridRenderScene,
    SlideRecoveryPageKind,
    SlideRecoveryResult,
)
from archium.exceptions import WorkflowError
from archium.infrastructure.database.repositories import PresentationRepository, ProjectRepository
from archium.infrastructure.database.visual_repositories import RenderSceneRepository
from tests.spike.slide_recovery_fixtures import SPIKE_SCENES


def _hybrid_from_scene(source_page_id: str = "title-page") -> HybridRenderScene:
    scene = SPIKE_SCENES[SlideRecoveryPageKind.TITLE].model_copy(deep=True)
    return HybridRenderScene(
        scene=scene,
        recovery_source_id=source_page_id,
        page_kind=SlideRecoveryPageKind.TITLE,
        reconstruction_fidelity=ExportFidelityLevel.HYBRID_EDITABLE,
    )


def test_export_builds_manifest_with_hybrid_fidelity(
    db_session,
    tmp_path: Path,
) -> None:
    project = ProjectRepository(db_session).create(Project(name="Recovery Export"))
    settings = Settings(_env_file=None, output_path=tmp_path)
    hybrid = _hybrid_from_scene()
    service = SlideRecoveryDeliveryService(db_session, settings=settings)

    with patch(
        "archium.application.slide_recovery_delivery_service.maybe_export_scene_pptx",
    ) as export_mock:
        pptx_path = tmp_path / "title-page.pptx"
        pptx_path.write_bytes(b"pptx")
        export_mock.return_value = pptx_path
        result = service.export_pptx(project.id, hybrid, source_page_id="title-page")

    assert result.manifest.final_fidelity == ExportFidelityLevel.FULLY_EDITABLE
    assert result.slide_export.fidelity_level == ExportFidelityLevel.FULLY_EDITABLE
    assert result.pptx_path is not None
    assert result.scene_preview_path is not None
    assert result.scene_preview_path.is_file()


def test_export_blocked_under_strict_native_policy(
    db_session,
    tmp_path: Path,
) -> None:
    project = ProjectRepository(db_session).create(Project(name="Recovery Strict"))
    settings = Settings(_env_file=None, output_path=tmp_path)
    scene = SPIKE_SCENES[SlideRecoveryPageKind.DRAWING_DOMINANT].model_copy(deep=True)
    hybrid = HybridRenderScene(
        scene=scene,
        recovery_source_id="drawing-page",
        page_kind=SlideRecoveryPageKind.DRAWING_DOMINANT,
        reconstruction_fidelity=ExportFidelityLevel.HYBRID_EDITABLE,
    )
    service = SlideRecoveryDeliveryService(db_session, settings=settings)

    with patch(
        "archium.application.slide_recovery_delivery_service.maybe_export_scene_pptx",
        return_value=tmp_path / "blocked.pptx",
    ):
        with pytest.raises(WorkflowError, match="忠实度"):
            service.export_pptx(
                project.id,
                hybrid,
                source_page_id="drawing-page",
                policy_preset="strict_native",
            )


def test_import_creates_slide_scene_and_recovery_revision(
    db_session,
    tmp_path: Path,
) -> None:
    project = ProjectRepository(db_session).create(Project(name="Recovery Import"))
    presentations = PresentationRepository(db_session)
    presentation = presentations.create_presentation(
        Presentation(project_id=project.id, title="Target Deck")
    )
    settings = Settings(_env_file=None, output_path=tmp_path)
    hybrid = _hybrid_from_scene("import-page")
    recovery = SlideRecoveryResult(
        source_page_id="import-page",
        reconstruction_fidelity=ExportFidelityLevel.HYBRID_EDITABLE,
        hybrid_scene=hybrid,
    )
    service = SlideRecoveryDeliveryService(db_session, settings=settings)

    result = service.import_to_presentation(
        project.id,
        hybrid,
        recovery,
        presentation_id=presentation.id,
    )

    slides = presentations.list_slides(presentation.id)
    assert len(slides) == 1
    assert slides[0].chapter_id == "recovery"
    assert slides[0].layout_plan_id is not None

    scenes = RenderSceneRepository(db_session).list_by_slide(result.slide_id)
    assert len(scenes) == 1
    assert scenes[0].slide_id == result.slide_id
    assert scenes[0].presentation_id == presentation.id

    revisions = service._scene_history.list_slide_scene_revisions(slides[0])
    assert revisions
    assert revisions[0].snapshot.get("scene_revision_source") == "import_recovery"


def test_import_creates_presentation_when_missing(
    db_session,
    tmp_path: Path,
) -> None:
    project = ProjectRepository(db_session).create(Project(name="Recovery Auto Deck"))
    settings = Settings(_env_file=None, output_path=tmp_path)
    hybrid = _hybrid_from_scene("auto-page")
    service = SlideRecoveryDeliveryService(db_session, settings=settings)

    result = service.import_to_presentation(project.id, hybrid, None)

    presentation = PresentationRepository(db_session).get_presentation(result.presentation_id)
    assert presentation is not None
    assert presentation.project_id == project.id
    assert result.slide_order == 0
