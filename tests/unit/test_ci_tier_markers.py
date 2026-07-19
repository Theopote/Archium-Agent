"""Guardrails for mutually exclusive CI pytest tier markers."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import _TIER_MARKERS, _TIER_PATH_PREFIXES, _tier_marker_for_path

pytestmark = pytest.mark.unit


def test_tier_path_prefixes_map_to_known_markers() -> None:
    tiers = {tier for _, tier in _TIER_PATH_PREFIXES}
    assert tiers == set(_TIER_MARKERS)


@pytest.mark.parametrize(
    ("relative_path", "expected_tier"),
    [
        ("tests/unit/test_settings.py", "unit"),
        ("tests/application/visual/test_composite_operations.py", "integration"),
        ("tests/integration/visual/test_e2e_benchmark_service.py", "integration"),
        ("tests/benchmark/architectural_slides/test_architectural_benchmark.py", "benchmark"),
        ("tests/e2e/real_projects/test_real_project_acceptance.py", "e2e"),
        ("tests/smoke/test_pptxgen_render.py", "smoke"),
        ("tests/golden/regression/test_regression_cases.py", None),
    ],
)
def test_tier_marker_for_path(relative_path: str, expected_tier: str | None) -> None:
    assert _tier_marker_for_path(Path(relative_path)) == expected_tier


def test_ci_tier_tests_have_at_most_one_primary_marker(request: pytest.FixtureRequest) -> None:
    session = request.session
    duplicates: list[str] = []
    for item in session.items:
        matched = [mark.name for mark in item.iter_markers() if mark.name in _TIER_MARKERS]
        if len(matched) > 1:
            duplicates.append(f"{item.nodeid}: {matched}")
    assert not duplicates, "Tests must not carry multiple CI tier markers:\n" + "\n".join(duplicates)
