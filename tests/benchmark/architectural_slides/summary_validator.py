"""Validate committed architectural benchmark summary reports."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from archium.domain.visual.benchmark import HumanVisualReview

from tests.benchmark.architectural_slides.artifacts import (
    BENCHMARK_ROOT,
    human_review_is_placeholder,
    materialized_benchmark_case_ids,
)
from tests.benchmark.architectural_slides.case_builders import build_benchmark_case
from tests.benchmark.architectural_slides.report_builder import build_benchmark_summary

BENCHMARK_REPORTS_DIR = BENCHMARK_ROOT / "reports"
BENCHMARK_SUMMARY_PATH = BENCHMARK_REPORTS_DIR / "benchmark-summary.json"
BENCHMARK_REPORT_PATH = BENCHMARK_REPORTS_DIR / "benchmark-report.html"

# Formal layout-rule quality gate (30/30 after Step 11 layout fixes).
BENCHMARK_RULE_PASS_RATE_THRESHOLD = 1.0

_CASE_ARTIFACT_NAMES = (
    "validation_report.json",
    "score_baseline.json",
    "deck_qa_report.json",
    "layout_plan.json",
    "render_manifest.json",
    "human_review.json",
    "layout_score.json",
)


def load_committed_summary(path: Path = BENCHMARK_SUMMARY_PATH) -> dict[str, Any]:
    if not path.exists():
        msg = f"Missing benchmark summary: {path}"
        raise AssertionError(msg)
    return json.loads(path.read_text(encoding="utf-8"))


def latest_case_artifact_mtime() -> float:
    mtimes: list[float] = []
    for case_id in materialized_benchmark_case_ids():
        directory = BENCHMARK_ROOT / case_id
        for name in _CASE_ARTIFACT_NAMES:
            path = directory / name
            if path.exists():
                mtimes.append(path.stat().st_mtime)
    if not mtimes:
        msg = "No benchmark case artifacts found for freshness check"
        raise AssertionError(msg)
    return max(mtimes)


def assert_summary_fresh(summary: dict[str, Any], *, tolerance_seconds: float = 1.0) -> None:
    generated_raw = summary.get("generated_at")
    if not isinstance(generated_raw, str):
        msg = "benchmark-summary.json missing generated_at"
        raise AssertionError(msg)
    generated_at = datetime.fromisoformat(generated_raw)
    if generated_at.tzinfo is None:
        generated_at = generated_at.replace(tzinfo=UTC)
    latest_artifact = datetime.fromtimestamp(latest_case_artifact_mtime(), tz=UTC)
    if generated_at.timestamp() + tolerance_seconds < latest_artifact.timestamp():
        msg = (
            "benchmark-summary.json is stale relative to case artifacts: "
            f"summary={generated_at.isoformat()} latest_artifact={latest_artifact.isoformat()}. "
            "Run: python scripts/build_architectural_benchmark_report.py"
        )
        raise AssertionError(msg)


def assert_human_reviews_not_scaffold_accepted() -> None:
    for case_id in materialized_benchmark_case_ids():
        path = BENCHMARK_ROOT / case_id / "human_review.json"
        review = HumanVisualReview.model_validate_json(path.read_text(encoding="utf-8"))
        if review.is_invalidated():
            assert not review.accepted, f"{case_id} invalidated review must not be accepted"
            continue
        if human_review_is_placeholder(review) and review.accepted:
            msg = (
                f"{case_id} human_review.json marks scaffold review as accepted=true "
                f"(source={review.source.value}). "
                "Only manual human reviews may set accepted=true."
            )
            raise AssertionError(msg)


def assert_summary_matches_live_build(summary: dict[str, Any]) -> None:
    expected = build_benchmark_summary(update=False)
    _compare_summary_payloads(summary, expected)


def assert_rule_pass_rate_meets_threshold(summary: dict[str, Any]) -> None:
    rate = float(summary.get("rule_pass_rate", 0.0))
    if rate + 1e-9 < BENCHMARK_RULE_PASS_RATE_THRESHOLD:
        msg = (
            f"benchmark rule_pass_rate {rate:.3f} below threshold "
            f"{BENCHMARK_RULE_PASS_RATE_THRESHOLD:.3f}"
        )
        raise AssertionError(msg)


def assert_committed_benchmark_reports_valid(
    *,
    summary_path: Path = BENCHMARK_SUMMARY_PATH,
    report_path: Path = BENCHMARK_REPORT_PATH,
) -> None:
    if not report_path.exists():
        msg = f"Missing benchmark report HTML: {report_path}"
        raise AssertionError(msg)
    summary = load_committed_summary(summary_path)
    materialized_ids = materialized_benchmark_case_ids()
    case_dirs = sorted(
        path.name
        for path in BENCHMARK_ROOT.iterdir()
        if path.is_dir() and path.name.startswith("case_")
    )
    if summary.get("case_count") != len(materialized_ids):
        msg = (
            f"summary case_count={summary.get('case_count')} "
            f"!= materialized baselines {len(materialized_ids)}"
        )
        raise AssertionError(msg)
    if len(case_dirs) != len(materialized_ids):
        msg = (
            f"benchmark directories={len(case_dirs)} "
            f"!= materialized baselines {len(materialized_ids)}"
        )
        raise AssertionError(msg)
    assert_summary_fresh(summary)
    assert_summary_matches_live_build(summary)
    assert_rule_pass_rate_meets_threshold(summary)
    assert_human_reviews_not_scaffold_accepted()


def _compare_summary_payloads(actual: dict[str, Any], expected: dict[str, Any]) -> None:
    keys = (
        "case_count",
        "rule_passed_count",
        "rule_pass_rate",
        "manual_human_review_count",
        "manual_human_accepted_count",
        "placeholder_human_review_count",
        "human_average_weighted_score",
        "human_quality_gate_passed",
        "human_quality_gate_reasons",
    )
    for key in keys:
        if actual.get(key) != expected.get(key):
            msg = f"summary {key} mismatch: committed={actual.get(key)!r} live={expected.get(key)!r}"
            raise AssertionError(msg)

    actual_cases = {item["case_id"]: item for item in actual.get("cases", [])}
    expected_cases = {item["case_id"]: item for item in expected.get("cases", [])}
    if set(actual_cases) != set(expected_cases):
        msg = "summary case_id set mismatch between committed summary and live build"
        raise AssertionError(msg)

    compare_fields = (
        "rule_passed",
        "layout_score",
        "has_critical",
        "render_valid",
        "render_source",
        "preview_png",
        "human_weighted_score",
        "human_score_label",
        "human_review_source",
        "human_review_validity",
        "human_accepted_for_delivery",
        "human_invalidated",
    )
    for case_id in materialized_benchmark_case_ids():
        row = actual_cases[case_id]
        live = expected_cases[case_id]
        for field in compare_fields:
            if row.get(field) != live.get(field):
                msg = (
                    f"{case_id} summary field {field} mismatch: "
                    f"committed={row.get(field)!r} live={live.get(field)!r}"
                )
                raise AssertionError(msg)

        result = build_benchmark_case(case_id)
        if row.get("rule_passed") != result.rule_score.passed:
            msg = f"{case_id} summary rule_passed disagrees with BenchmarkRuleScore"
            raise AssertionError(msg)
        if abs(float(row.get("layout_score", 0.0)) - result.rule_score.layout_score) > 1e-6:
            msg = f"{case_id} summary layout_score disagrees with BenchmarkRuleScore"
            raise AssertionError(msg)
