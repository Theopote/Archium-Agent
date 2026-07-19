"""LayoutPlan PPTX screenshot regression — rasterized slide vs committed baseline PNG."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from archium.application.visual.visual_intent_service import VisualIntentService
from archium.config.settings import Settings
from archium.infrastructure.renderers.pptxgen_cli import PptxGenCliRunner
from tests.golden.visual.composition.case_builders import build_composition_case
from tests.golden.visual.composition.screenshot_baseline import (
    SCREENSHOT_CASE_IDS,
    UPDATE_ENV,
    compare_screenshot_to_baseline,
    render_case_pptx_screenshot,
    save_screenshot_baseline,
    screenshot_baseline_path,
    screenshot_tools_available,
    update_mode_enabled,
)

pytestmark = [pytest.mark.regression, pytest.mark.layout_pptx_screenshot]

GOLDEN_ROOT = Path(__file__).resolve().parent


class _FakeIntentRepo:
    def __init__(self) -> None:
        self._items: dict = {}

    def save(self, intent):  # noqa: ANN001
        self._items[intent.id] = intent
        return intent

    def get(self, intent_id):  # noqa: ANN001
        return self._items.get(intent_id)


@pytest.fixture
def intent_service() -> VisualIntentService:
    service = VisualIntentService.__new__(VisualIntentService)
    service._session = None  # noqa: SLF001
    service._llm = None  # noqa: SLF001
    service._intents = _FakeIntentRepo()  # noqa: SLF001
    return service


def _pptxgen_available() -> bool:
    if shutil.which("node") is None:
        return False
    runner = PptxGenCliRunner(Settings(_env_file=None))
    return runner.is_available() and runner.layout_plan_script_path.exists()


@pytest.mark.parametrize("case_id", SCREENSHOT_CASE_IDS)
def test_layout_pptx_screenshot_matches_baseline(
    intent_service: VisualIntentService,
    case_id: str,
    tmp_path: Path,
) -> None:
    if not _pptxgen_available():
        pytest.skip("PptxGenJS runtime unavailable — run npm ci in archium/infrastructure/renderers/pptxgen")
    if not screenshot_tools_available():
        pytest.skip("LibreOffice + pdftoppm required for LayoutPlan PPTX screenshot regression")

    case = build_composition_case(case_id, intent_service)
    case_dir = GOLDEN_ROOT / case_id
    actual = render_case_pptx_screenshot(case, tmp_path / case_id)
    assert actual is not None, f"{case_id}: failed to render PPTX screenshot"

    if update_mode_enabled():
        saved = save_screenshot_baseline(case_dir, case=case, screenshot_path=actual)
        pytest.skip(f"Updated screenshot baseline: {saved}")

    baseline = screenshot_baseline_path(case_dir)
    if not baseline.is_file():
        pytest.fail(
            f"{case_id}: missing committed baseline {baseline.name}. "
            f"Run: {UPDATE_ENV}=1 python scripts/update_layout_pptx_screenshot_baselines.py"
        )

    issues = compare_screenshot_to_baseline(case_dir, actual)
    assert not issues, f"{case_id} screenshot regression failed:\n- " + "\n- ".join(issues)


def test_screenshot_case_manifests_exist() -> None:
    for case_id in SCREENSHOT_CASE_IDS:
        case_dir = GOLDEN_ROOT / case_id
        baseline = screenshot_baseline_path(case_dir)
        if not baseline.is_file():
            pytest.skip(f"Screenshot baselines not committed yet (missing {baseline})")
        from tests.golden.visual.composition.screenshot_baseline import load_screenshot_manifest

        manifest = load_screenshot_manifest(case_dir)
        assert manifest.case_id == case_id
        assert manifest.screenshot.file == baseline.name


def test_update_env_documented() -> None:
    assert UPDATE_ENV == "UPDATE_LAYOUT_PPTX_SCREENSHOT_GOLDENS"
