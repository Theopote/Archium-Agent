"""Layer 3: live model evaluation (manual / scheduled, not default CI)."""

from __future__ import annotations

import os

import pytest

pytestmark = [
    pytest.mark.live_llm,
    pytest.mark.skipif(
        os.environ.get("ARCHIUM_LIVE_LLM") != "1",
        reason="Live LLM evaluation requires ARCHIUM_LIVE_LLM=1 and configured API keys",
    ),
]


def test_live_model_evaluation_placeholder() -> None:
    """Placeholder — implement periodic quality review against real LLM providers."""
    pytest.skip(
        "Live model evaluation is manual. "
        "Copy a regression manifest, point to real fixtures, and review outputs offline."
    )
