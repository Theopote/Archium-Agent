"""Pytest markers and shared config for golden acceptance layers."""

from __future__ import annotations

import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "regression: Layer 1 deterministic workflow regression (CI)")
    config.addinivalue_line(
        "markers",
        "visual_regression: PNG preview baseline checks for key Golden Cases (requires Marp CLI)",
    )
    config.addinivalue_line("markers", "smoke: End-to-end smoke tests (PptxGenJS, real parsers)")
    config.addinivalue_line(
        "markers",
        "fixture_acceptance: Layer 2 real parser + cached/mock LLM (CI when fixtures present)",
    )
    config.addinivalue_line(
        "markers",
        "live_llm: Layer 3 live model evaluation (manual / scheduled only, not default CI)",
    )
