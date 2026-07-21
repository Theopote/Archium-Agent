"""Hard budget for committed architectural-slide Golden binaries."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.benchmark.architectural_slides.artifacts import BENCHMARK_ROOT, case_dir, materialized_benchmark_case_ids

# Keep in sync with README.md § 二进制大小上限 (hard limits only).
HARD_PNG_BYTES = 2 * 1024 * 1024
HARD_PPTX_BYTES = 5 * 1024 * 1024
HARD_CASE_BYTES = 8 * 1024 * 1024
HARD_SUITE_BYTES = 80 * 1024 * 1024

_BINARY_SUFFIXES = {".png", ".pptx"}


def _binary_files(directory: Path) -> list[Path]:
    return [
        path
        for path in directory.rglob("*")
        if path.is_file() and path.suffix.lower() in _BINARY_SUFFIXES
    ]


@pytest.mark.benchmark
@pytest.mark.architectural_benchmark
def test_golden_binary_hard_budget() -> None:
    """Fail if committed Goldens exceed documented hard size limits."""
    offenders: list[str] = []
    suite_total = 0
    for case_id in materialized_benchmark_case_ids():
        directory = case_dir(case_id)
        case_total = 0
        for path in _binary_files(directory):
            size = path.stat().st_size
            case_total += size
            suite_total += size
            rel = path.relative_to(BENCHMARK_ROOT).as_posix()
            if path.suffix.lower() == ".png" and size > HARD_PNG_BYTES:
                offenders.append(f"{rel}: png {size} > {HARD_PNG_BYTES}")
            if path.suffix.lower() == ".pptx" and size > HARD_PPTX_BYTES:
                offenders.append(f"{rel}: pptx {size} > {HARD_PPTX_BYTES}")
        if case_total > HARD_CASE_BYTES:
            offenders.append(f"{case_id}: case binaries {case_total} > {HARD_CASE_BYTES}")
    if suite_total > HARD_SUITE_BYTES:
        offenders.append(f"suite binaries {suite_total} > {HARD_SUITE_BYTES}")
    assert not offenders, "Golden binary hard budget exceeded:\n" + "\n".join(offenders)
