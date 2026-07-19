"""Build architectural benchmark cases via BenchmarkService."""

from __future__ import annotations

from archium.application.visual.benchmark_service import BenchmarkCaseResult, BenchmarkService

from tests.benchmark.architectural_slides.case_registry import (
    BENCHMARK_CASE_IDS,
    build_case_request,
    get_case_definition,
)


def build_benchmark_case(case_id: str, *, service: BenchmarkService | None = None) -> BenchmarkCaseResult:
    builder = service or BenchmarkService()
    return builder.build_case(build_case_request(case_id))


__all__ = [
    "BENCHMARK_CASE_IDS",
    "build_benchmark_case",
    "get_case_definition",
]
