"""Architectural slide benchmark tests."""

from __future__ import annotations

import pytest
from archium.domain.visual.benchmark import (
    ArchitecturalSlideCategory,
    HUMAN_REVIEW_PASS_THRESHOLD,
    HumanVisualReview,
)
from archium.domain.visual.enums import CropPolicy, ImageFit, LayoutElementRole, LayoutFamily

from tests.benchmark.architectural_slides.artifacts import (
    UPDATE_ENV,
    assert_or_update_case_baseline,
    case_dir,
    default_human_review,
)
from tests.benchmark.architectural_slides.case_builders import build_benchmark_case
from tests.benchmark.architectural_slides.case_catalog import CASE_CATALOG
from tests.benchmark.architectural_slides.case_registry import (
    BENCHMARK_CASE_IDS,
    get_case_definition,
)

pytestmark = pytest.mark.architectural_benchmark


def test_benchmark_catalog_has_thirty_cases() -> None:
    assert len(CASE_CATALOG) == 30
    assert len(BENCHMARK_CASE_IDS) == 30
    assert len(set(BENCHMARK_CASE_IDS)) == 30


def test_benchmark_covers_all_layout_families() -> None:
    families = {entry.definition.expected_layout_family for entry in CASE_CATALOG}
    assert families == set(LayoutFamily)


def test_benchmark_covers_all_categories() -> None:
    categories = {entry.definition.category for entry in CASE_CATALOG}
    assert categories == set(ArchitecturalSlideCategory)


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
    blocking = [
        issue
        for issue in result.report.issues
        if issue.severity.value in {"error", "critical"}
    ]
    assert not blocking, f"{case_id} has blocking layout issues: {[issue.rule_code for issue in blocking]}"
    assert result.rule_score.passed, f"{case_id} failed layout rule score"
    assert_or_update_case_baseline(result)


def test_benchmark_rule_pass_rate_meets_eighty_percent() -> None:
    passed = sum(1 for case_id in BENCHMARK_CASE_IDS if build_benchmark_case(case_id).rule_score.passed)
    assert passed / len(BENCHMARK_CASE_IDS) >= 0.8


_CATEGORY_MINIMUMS: dict[ArchitecturalSlideCategory, int] = {
    ArchitecturalSlideCategory.DRAWING: 10,
    ArchitecturalSlideCategory.PHOTO_ANALYSIS: 8,
    ArchitecturalSlideCategory.CASE_COMPARISON: 5,
    ArchitecturalSlideCategory.DATA_METRICS: 4,
    ArchitecturalSlideCategory.TEXT_NARRATIVE: 3,
}


def test_benchmark_category_minimums() -> None:
    counts: dict[ArchitecturalSlideCategory, int] = dict.fromkeys(ArchitecturalSlideCategory, 0)
    for entry in CASE_CATALOG:
        counts[entry.definition.category] += 1
    for category, minimum in _CATEGORY_MINIMUMS.items():
        assert counts[category] >= minimum, (
            f"{category.value} has {counts[category]} cases, expected at least {minimum}"
        )


def test_benchmark_human_review_meets_threshold() -> None:
    scores: list[float] = []
    for case_id in BENCHMARK_CASE_IDS:
        path = case_dir(case_id) / "human_review.json"
        review = HumanVisualReview.model_validate_json(path.read_text(encoding="utf-8"))
        assert review.passes_threshold(HUMAN_REVIEW_PASS_THRESHOLD), (
            f"{case_id} human review below {HUMAN_REVIEW_PASS_THRESHOLD}: "
            f"{review.weighted_score()}"
        )
        assert review.accepted, f"{case_id} human review not accepted"
        scores.append(review.weighted_score())
    assert sum(scores) / len(scores) >= HUMAN_REVIEW_PASS_THRESHOLD


def test_default_human_review_template_passes_threshold() -> None:
    review = default_human_review("case_001_site_plan")
    assert review.passes_threshold(HUMAN_REVIEW_PASS_THRESHOLD)
    assert review.accepted


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
