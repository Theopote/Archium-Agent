"""Layer 1 visual regression — PNG preview baselines for key Golden Cases."""

from __future__ import annotations

import pytest
from archium.infrastructure.renderers.marp_cli import MarpCliRunner
from tests.golden.visual.baseline import (
    VISUAL_CASE_IDS,
    compare_to_baseline,
    load_baseline,
)
from tests.golden.visual.runner import run_visual_baseline_case

pytestmark = [pytest.mark.regression, pytest.mark.visual_regression]


def _marp_available(test_settings: object) -> bool:
    return MarpCliRunner(test_settings).is_available()  # type: ignore[arg-type]


@pytest.mark.parametrize("case_id", VISUAL_CASE_IDS)
def test_visual_regression_matches_baseline(
    db_session: object,
    test_settings: object,
    case_id: str,
) -> None:
    if not _marp_available(test_settings):
        pytest.skip("Marp CLI unavailable — install @marp-team/marp-cli to run visual regression")

    settings = test_settings.model_copy(  # type: ignore[attr-defined]
        update={
            "marp_preview_images_enabled": True,
            "marp_preview_image_format": "png",
        }
    )
    run = run_visual_baseline_case(db_session, settings, case_id)  # type: ignore[arg-type]
    baseline = load_baseline(case_id)
    issues = compare_to_baseline(
        baseline,
        slides=list(run.workflow.slides),
        preview_paths=list(run.preview_paths),
    )
    assert not issues, "Visual regression failed:\n- " + "\n- ".join(issues)


def test_visual_baseline_manifests_exist() -> None:
    for case_id in VISUAL_CASE_IDS:
        baseline = load_baseline(case_id)
        assert baseline.case_id == case_id
        assert baseline.preview_count >= baseline.slide_count
        assert baseline.slide_count >= 4
        assert baseline.preview_count >= 4
