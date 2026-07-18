"""Layer 3: live presentation-pipeline evaluation (manual / scheduled).

Mission M1–M6 live scoring lives in ``test_live_mission_evaluation.py`` and
``scripts/eval_mission_live.py``. This module remains for Brief/Storyline live runs.
"""

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


def test_live_presentation_evaluation_points_to_checklist() -> None:
    """Presentation live eval is checklist-driven; Mission live eval is implemented."""
    pytest.skip(
        "Presentation live eval: follow tests/golden/live/EVALUATION_CHECKLIST.md section B. "
        "For Mission M1–M6, run: py scripts/eval_mission_live.py"
    )
