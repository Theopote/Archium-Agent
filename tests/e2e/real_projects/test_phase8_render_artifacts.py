"""Phase 8 real-project RenderScene deliverable artifact checklist."""

from __future__ import annotations

from pathlib import Path

import pytest
from archium.domain.project_acceptance import REAL_PROJECT_MIN_SLIDES

from tests.e2e.real_projects.loader import load_manifest
from tests.e2e.real_projects.phase7_loader import (
    list_phase7_project_ids,
    load_phase7_project,
    resolve_input_manifest_path,
)
from tests.e2e.real_projects.phase8_artifacts import (
    HARD_REQUIRED,
    SOFT_OPTIONAL,
    assert_phase8_hard_artifacts,
    inspect_phase8_artifacts,
)
from tests.e2e.real_projects.phase8_runner import run_phase8_project

pytestmark = [
    pytest.mark.phase8_artifacts,
    pytest.mark.e2e,
]


def test_phase8_hard_soft_checklist_names() -> None:
    assert "presentation.pptx" in HARD_REQUIRED
    assert "presentation.pdf" in SOFT_OPTIONAL
    assert "pptx_screenshots" in SOFT_OPTIONAL


@pytest.mark.parametrize("project_id", list_phase7_project_ids())
def test_phase8_render_artifacts_pipeline(
    db_session,
    test_settings,
    project_id: str,
    tmp_path: Path,
) -> None:
    """Generate full Phase 8 outputs under tests/e2e/real_projects/<id>/outputs/."""
    bundle = load_phase7_project(project_id)
    manifest_path = resolve_input_manifest_path(bundle)
    loaded = load_manifest(manifest_path)
    min_slides = int(loaded.manifest.expectations.get("min_slides", REAL_PROJECT_MIN_SLIDES))

    summary = run_phase8_project(
        project_id,
        session=db_session,
        settings=test_settings,
        scratch_dir=tmp_path,
    )

    assert summary.succeeded, f"{project_id} soft_notes={summary.soft_notes}"
    assert summary.slide_count >= min_slides
    checklist = assert_phase8_hard_artifacts(project_id, min_slides=min_slides)
    assert checklist.counts_aligned
    # Soft artifacts may be absent without LibreOffice/pdftoppm.
    inspected = inspect_phase8_artifacts(project_id)
    assert isinstance(inspected.notes, list)
