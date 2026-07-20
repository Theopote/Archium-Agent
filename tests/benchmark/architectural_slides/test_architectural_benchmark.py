"""Architectural slide benchmark tests."""

from __future__ import annotations

import os

import pytest
from archium.domain.visual.benchmark import (
    HUMAN_REVIEW_PASS_THRESHOLD,
    ArchitecturalSlideCategory,
    HumanVisualReview,
)
from archium.domain.visual.enums import CropPolicy, ImageFit, LayoutElementRole, LayoutFamily

from tests.benchmark.architectural_slides.artifacts import (
    STRICT_HUMAN_REVIEW_ENV,
    UPDATE_ENV,
    assert_or_update_case_baseline,
    case_dir,
    default_human_review,
    derive_benchmark_human_review,
    human_review_is_placeholder,
    materialized_benchmark_case_ids,
)
from tests.benchmark.architectural_slides.case_builders import build_benchmark_case
from tests.benchmark.architectural_slides.case_catalog import CASE_CATALOG
from tests.benchmark.architectural_slides.case_registry import (
    BENCHMARK_CASE_IDS,
    get_case_definition,
)
from tests.benchmark.architectural_slides.summary_validator import (
    BENCHMARK_RULE_PASS_RATE_THRESHOLD,
    assert_committed_benchmark_reports_valid,
)

pytestmark = [pytest.mark.benchmark, pytest.mark.architectural_benchmark]


def test_benchmark_catalog_has_thirty_formal_cases_and_four_edge_entries() -> None:
    from tests.benchmark.architectural_slides.case_catalog import EDGE_CASE_CATALOG, FULL_CASE_CATALOG
    from tests.benchmark.architectural_slides.case_registry import (
        ALL_BENCHMARK_CASE_IDS,
        EDGE_BENCHMARK_CASE_IDS,
    )

    assert len(CASE_CATALOG) == 30
    assert len(BENCHMARK_CASE_IDS) == 30
    assert len(set(BENCHMARK_CASE_IDS)) == 30
    assert len(FULL_CASE_CATALOG) == 34
    assert len(ALL_BENCHMARK_CASE_IDS) == 34
    assert len(materialized_benchmark_case_ids()) == 30
    assert len(EDGE_CASE_CATALOG) == 4
    assert len(EDGE_BENCHMARK_CASE_IDS) == 4


def test_benchmark_covers_all_layout_families() -> None:
    families = {entry.definition.expected_layout_family for entry in CASE_CATALOG}
    assert families == set(LayoutFamily)


def test_benchmark_covers_all_categories() -> None:
    categories = {entry.definition.category for entry in CASE_CATALOG}
    assert categories == set(ArchitecturalSlideCategory)


@pytest.mark.parametrize("case_id", materialized_benchmark_case_ids())
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


def test_benchmark_rule_pass_rate_meets_threshold() -> None:
    materialized = materialized_benchmark_case_ids()
    passed = sum(
        1 for case_id in materialized if build_benchmark_case(case_id).rule_score.passed
    )
    rate = passed / len(materialized)
    assert rate + 1e-9 >= BENCHMARK_RULE_PASS_RATE_THRESHOLD, (
        f"layout rule pass rate {rate:.3f} below {BENCHMARK_RULE_PASS_RATE_THRESHOLD}"
    )


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


def test_benchmark_human_review_scaffold_not_marked_accepted() -> None:
    strict = os.environ.get(STRICT_HUMAN_REVIEW_ENV) == "1"
    for case_id in materialized_benchmark_case_ids():
        path = case_dir(case_id) / "human_review.json"
        review = HumanVisualReview.model_validate_json(path.read_text(encoding="utf-8"))
        if review.is_invalidated():
            assert not review.accepted_for_delivery
            assert review.validity.value == "invalid_render_artifact"
            continue
        if human_review_is_placeholder(review):
            assert not review.accepted, (
                f"{case_id} scaffold human review must not set accepted=true "
                f"(source={review.source.value})"
            )
            if strict:
                pytest.fail(
                    f"{case_id} still uses placeholder human review; "
                    "replace with manual review before quality acceptance"
                )
            continue
        assert review.is_manual_review(), f"{case_id} human review must be manual"
        assert review.passes_threshold(HUMAN_REVIEW_PASS_THRESHOLD)
        assert review.accepted_for_delivery, f"{case_id} manual human review not accepted for delivery"


def test_benchmark_summary_report_is_current_and_consistent() -> None:
    assert_committed_benchmark_reports_valid()


def test_default_human_review_template_passes_threshold() -> None:
    review = default_human_review("case_001_site_plan")
    assert review.passes_threshold(HUMAN_REVIEW_PASS_THRESHOLD)
    assert not review.accepted
    assert human_review_is_placeholder(review)


def test_derived_benchmark_human_review_is_scaffold() -> None:
    review = derive_benchmark_human_review(
        "case_001_site_plan",
        layout_score=0.92,
        layout_valid=True,
    )
    assert review.passes_threshold(HUMAN_REVIEW_PASS_THRESHOLD)
    assert human_review_is_placeholder(review)
    assert review.source.value == "layout_qa_derived"


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
