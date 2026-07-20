"""Phase 7 automated pipeline acceptance (manual sign-off still required)."""

from __future__ import annotations

from pathlib import Path

import pytest
from archium.domain.project_acceptance import (
    REAL_PROJECT_MIN_ASSETS,
    REAL_PROJECT_MIN_SLIDES,
    HumanMetricsSource,
)

from tests.e2e.real_projects.loader import load_manifest
from tests.e2e.real_projects.phase7_artifacts import UPDATE_ENV
from tests.e2e.real_projects.phase7_loader import (
    list_phase7_project_ids,
    load_phase7_project,
    resolve_input_manifest_path,
)
from tests.e2e.real_projects.phase7_runner import run_phase7_acceptance_case

pytestmark = pytest.mark.phase7_acceptance


@pytest.mark.parametrize("project_id", list_phase7_project_ids())
def test_phase7_pending_artifacts_are_not_synthetic_signoff(project_id: str) -> None:
    bundle = load_phase7_project(project_id)
    research = (bundle.root / "research_report.json").read_text(encoding="utf-8")
    outline = (bundle.root / "outline_plan.json").read_text(encoding="utf-8")
    assert '"status": "pending"' in research
    assert "pending" in outline
    assert bundle.human_review is not None
    assert bundle.human_review.reviews == []


@pytest.mark.parametrize("project_id", list_phase7_project_ids())
def test_phase7_automated_pipeline_does_not_fill_manual_metrics(
    db_session,
    test_settings,
    project_id: str,
    tmp_path: Path,
) -> None:
    """Task book #16 — automated runs must not write studio_manual human scores."""
    bundle = load_phase7_project(project_id)
    manifest_path = resolve_input_manifest_path(bundle)
    loaded = load_manifest(manifest_path)
    summary = run_phase7_acceptance_case(
        project_id,
        session=db_session,
        settings=test_settings,
        scratch_dir=tmp_path,
    )

    min_slides = int(loaded.manifest.expectations.get("min_slides", REAL_PROJECT_MIN_SLIDES))
    min_assets = int(loaded.manifest.expectations.get("min_assets", REAL_PROJECT_MIN_ASSETS))

    assert summary.succeeded
    assert summary.slide_count >= REAL_PROJECT_MIN_SLIDES
    if project_id == "renovation_001":
        assert summary.slide_count >= min_slides
        assert summary.asset_count >= min_assets

    record = summary.record
    assert record.human_metrics_source != HumanMetricsSource.STUDIO_MANUAL
    assert record.human_rehearsal_passed is False
    assert record.metrics.average_human_visual_score is None
    assert record.metrics.major_edit_page_ratio is None
    assert record.metrics.user_edit_minutes is None
    assert record.metrics.top_dissatisfactions == []
    assert record.metrics.top_satisfactions == []


def test_phase7_update_env_documented() -> None:
    assert UPDATE_ENV == "UPDATE_PHASE7_ACCEPTANCE_RECORDS"
