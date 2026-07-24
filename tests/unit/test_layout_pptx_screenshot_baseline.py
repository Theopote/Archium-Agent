"""Unit tests for LayoutPlan PPTX screenshot baseline helpers."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from tests.golden.visual.composition.case_builders import build_composition_case
from tests.golden.visual.composition.screenshot_baseline import (
    compare_screenshot_to_baseline,
    save_screenshot_baseline,
)


class _FakeIntentRepo:
    def __init__(self) -> None:
        self._items: dict = {}

    def save(self, intent):  # noqa: ANN001
        self._items[intent.id] = intent
        return intent

    def get(self, intent_id):  # noqa: ANN001
        return self._items.get(intent_id)


@pytest.fixture
def intent_service():
    from archium.application.visual.visual_intent_service import VisualIntentService
    from archium.config.settings import get_settings

    service = VisualIntentService.__new__(VisualIntentService)
    service._session = None  # noqa: SLF001
    service._llm = None  # noqa: SLF001
    service._settings = get_settings()  # noqa: SLF001
    service._intents = _FakeIntentRepo()  # noqa: SLF001
    return service


def test_save_and_compare_screenshot_baseline(
    intent_service,
    tmp_path: Path,
) -> None:
    case = build_composition_case("v1_drawing_focus", intent_service)
    case_dir = tmp_path / case.case_id
    screenshot = tmp_path / "actual.png"
    Image.new("RGB", (640, 360), color=(248, 248, 246)).save(screenshot)

    saved = save_screenshot_baseline(case_dir, case=case, screenshot_path=screenshot)
    assert saved.is_file()
    assert (case_dir / "pptx_screenshot_manifest.json").is_file()

    issues = compare_screenshot_to_baseline(case_dir, screenshot)
    assert not issues

    mutated = tmp_path / "mutated.png"
    Image.new("RGB", (640, 360), color=(20, 20, 20)).save(mutated)
    drift = compare_screenshot_to_baseline(case_dir, mutated)
    assert drift
