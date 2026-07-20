"""Pytest hooks for architectural slide benchmark maintenance."""

from __future__ import annotations

import os

import pytest

from tests.benchmark.architectural_slides.artifacts import BENCHMARK_REPORTS_DIR, UPDATE_ENV
from tests.benchmark.architectural_slides.report_builder import write_benchmark_report


@pytest.fixture(scope="session", autouse=True)
def _regenerate_benchmark_reports_after_baseline_update() -> None:
    yield
    if os.environ.get(UPDATE_ENV) == "1":
        write_benchmark_report(BENCHMARK_REPORTS_DIR, update=False, from_disk_only=True)
