"""Real-project acceptance end-to-end tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from archium.domain.project_acceptance import (
    REAL_PROJECT_MIN_ASSETS,
    REAL_PROJECT_MIN_SLIDES,
    RealProjectAcceptanceRecord,
    RealProjectScenario,
)

from tests.e2e.real_projects.artifacts import UPDATE_ENV
from tests.e2e.real_projects.loader import list_manifest_paths, load_manifest
from tests.e2e.real_projects.runner import run_acceptance_case

pytestmark = pytest.mark.real_project_acceptance


def test_real_project_manifests_cover_five_scenarios() -> None:
    paths = list_manifest_paths()
    assert len(paths) == 5
    scenarios = {load_manifest(path).manifest.scenario for path in paths}
    assert scenarios == set(RealProjectScenario)


@pytest.mark.parametrize(
    "manifest_path",
    list_manifest_paths(),
    ids=lambda path: path.stem,
)
def test_real_project_acceptance_case(
    db_session,
    test_settings,
    manifest_path: Path,
    tmp_path: Path,
) -> None:
    loaded = load_manifest(manifest_path)
    summary = run_acceptance_case(
        manifest_path,
        session=db_session,
        settings=test_settings,
        scratch_dir=tmp_path,
    )

    min_slides = int(loaded.manifest.expectations.get("min_slides", REAL_PROJECT_MIN_SLIDES))
    min_assets = int(loaded.manifest.expectations.get("min_assets", REAL_PROJECT_MIN_ASSETS))

    assert summary.slide_count >= min_slides
    assert summary.asset_count >= min_assets
    assert summary.succeeded
    assert summary.record_path.exists()
    record = RealProjectAcceptanceRecord.model_validate_json(
        summary.record_path.read_text(encoding="utf-8")
    )
    assert record.human_metrics_source != "studio_manual"
    assert record.human_rehearsal_passed is False
    assert record.metrics.average_human_visual_score is None


def test_update_env_documented() -> None:
    assert UPDATE_ENV == "UPDATE_REAL_PROJECT_ACCEPTANCE_RECORDS"
