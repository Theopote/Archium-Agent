"""Architectural slide benchmark tests."""

from __future__ import annotations

import pytest
from archium.domain.visual.enums import CropPolicy, ImageFit, LayoutElementRole, LayoutFamily

from tests.benchmark.architectural_slides.artifacts import (
    UPDATE_ENV,
    assert_or_update_case_baseline,
)
from tests.benchmark.architectural_slides.case_builders import build_benchmark_case
from tests.benchmark.architectural_slides.case_registry import (
    BENCHMARK_CASE_IDS,
    get_case_definition,
)

pytestmark = pytest.mark.architectural_benchmark


@pytest.mark.parametrize("case_id", BENCHMARK_CASE_IDS)
def test_architectural_benchmark_case(case_id: str) -> None:
    result = build_benchmark_case(case_id)
    definition = get_case_definition(case_id)

    assert result.plan.layout_family == definition.expected_layout_family
    assert result.plan.layout_variant == definition.layout_variant
    assert not result.report.has_critical(), (
        f"{case_id} has critical layout issues: "
        f"{[issue.rule_code for issue in result.report.issues if issue.severity.value == 'critical']}"
    )
    assert_or_update_case_baseline(result)


def test_case_001_drawing_hero_constraints() -> None:
    result = build_benchmark_case("case_001_site_plan")
    hero = result.plan.element_by_id("hero")
    assert hero is not None
    assert hero.fit_mode == ImageFit.CONTAIN
    assert hero.crop_policy == CropPolicy.FORBIDDEN
    assert result.plan.elements_by_role(LayoutElementRole.SOURCE)


def test_case_002_evidence_grid_uniformity() -> None:
    result = build_benchmark_case("case_002_site_photos")
    photos = result.plan.elements_by_role(LayoutElementRole.SUPPORTING_VISUAL)
    assert len(photos) == 4
    assert len({round(item.width, 3) for item in photos}) == 1


def test_case_003_comparative_matrix() -> None:
    result = build_benchmark_case("case_003_case_comparison")
    assert result.plan.layout_family == LayoutFamily.COMPARATIVE_MATRIX
    images = result.plan.elements_by_role(LayoutElementRole.SUPPORTING_VISUAL)
    assert len(images) == 3


def test_case_004_metric_dashboard() -> None:
    result = build_benchmark_case("case_004_economic_metrics")
    assert len(result.plan.elements_by_role(LayoutElementRole.METRIC)) == 5
    assert result.plan.element_by_id("chart") is not None


def test_case_005_textual_argument() -> None:
    result = build_benchmark_case("case_005_design_concept")
    assert result.plan.layout_family == LayoutFamily.TEXTUAL_ARGUMENT
    assert result.plan.elements_by_role(LayoutElementRole.LEAD_STATEMENT)
    assert result.plan.elements_by_role(LayoutElementRole.BODY_TEXT)


def test_update_env_documented() -> None:
    assert UPDATE_ENV == "UPDATE_ARCHITECTURAL_BENCHMARK_BASELINES"
