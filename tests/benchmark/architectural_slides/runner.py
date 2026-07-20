"""Run architectural slide benchmark cases."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from archium.application.visual.benchmark_service import BenchmarkCaseResult, BenchmarkService

from tests.benchmark.architectural_slides.artifacts import (
    BENCHMARK_ROOT,
    assert_or_update_case_baseline,
    case_dir,
    materialized_benchmark_case_ids,
    write_case_artifacts,
)
from tests.benchmark.architectural_slides.case_builders import build_benchmark_case
from tests.benchmark.architectural_slides.case_registry import ALL_BENCHMARK_CASE_IDS, BENCHMARK_CASE_IDS


@dataclass(frozen=True)
class BenchmarkRunSummary:
    case_id: str
    passed: bool
    layout_score: float
    has_critical: bool
    case_dir: Path


def run_case(
    case_id: str,
    *,
    service: BenchmarkService | None = None,
    update: bool = False,
) -> BenchmarkRunSummary:
    result = build_benchmark_case(case_id, service=service)
    if update:
        write_case_artifacts(result)
    else:
        assert_or_update_case_baseline(result)
    return BenchmarkRunSummary(
        case_id=case_id,
        passed=result.rule_score.passed,
        layout_score=result.rule_score.layout_score,
        has_critical=result.rule_score.has_critical,
        case_dir=case_dir(case_id),
    )


def run_all_cases(
    *,
    service: BenchmarkService | None = None,
    update: bool = False,
) -> list[BenchmarkRunSummary]:
    case_ids = ALL_BENCHMARK_CASE_IDS if update else materialized_benchmark_case_ids()
    return [run_case(case_id, service=service, update=update) for case_id in case_ids]


def load_case_result(case_id: str, *, service: BenchmarkService | None = None) -> BenchmarkCaseResult:
    return build_benchmark_case(case_id, service=service)


__all__ = ["BENCHMARK_ROOT", "BenchmarkRunSummary", "load_case_result", "run_all_cases", "run_case"]
