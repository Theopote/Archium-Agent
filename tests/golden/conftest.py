"""Pytest markers and shared config for golden acceptance layers."""

from __future__ import annotations

import pytest


def pytest_configure(config: pytest.Config) -> None:
    # Prefer pyproject.toml as the marker registry; keep local lines only for
    # golden-layer markers that nested suites historically relied on.
    config.addinivalue_line("markers", "regression: Layer 1 deterministic workflow regression (CI)")
    config.addinivalue_line(
        "markers",
        "fixture_acceptance: Layer 2 real parser + cached/mock LLM (CI when fixtures present)",
    )
    config.addinivalue_line(
        "markers",
        "live_llm: Layer 3 live model evaluation (manual / scheduled only, not default CI)",
    )
