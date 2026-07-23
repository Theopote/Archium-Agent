"""LayoutPlan PPTX screenshot regression — final deliverable track.

Track: ``pptx_visual_regression``
  LayoutPlan → PptxGenJS → PPTX → LibreOffice/PowerPoint → pptx_screenshot.png

This is **not** the Python wireframe preview track
(``preview_visual_regression`` / ``test_golden_cases.py``).

Baseline updates require: generate candidates → human review → approve-baseline.
Pytest never overwrites committed baselines.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from archium.application.visual.visual_intent_service import VisualIntentService
from archium.config.settings import Settings
from archium.infrastructure.renderers.pptxgen_cli import PptxGenCliRunner
from tests.golden.visual.composition.case_builders import build_composition_case
from tests.golden.visual.composition.screenshot_baseline import (
    CANDIDATE_ENV,
    PPTX_VISUAL_REGRESSION_CASE_IDS,
    candidate_mode_enabled,
    compare_screenshot_to_baseline,
    render_case_pptx_screenshot,
    save_screenshot_candidate,
    screenshot_baseline_path,
    screenshot_tools_available,
)
from tests.golden.visual.composition.visual_regression_tracks import (
    PPTX_MARKER,
    PPTX_MARKER_LEGACY,
)

pytestmark = [
    pytest.mark.regression,
    pytest.mark.pptx_visual_regression,
    pytest.mark.layout_pptx_screenshot,
]

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
    from archium.config.settings import get_settings

    service = VisualIntentService.__new__(VisualIntentService)
    service._session = None  # noqa: SLF001
    service._llm = None  # noqa: SLF001
    service._settings = get_settings()  # noqa: SLF001
    service._intents = _FakeIntentRepo()  # noqa: SLF001
    return service


def _pptxgen_available() -> bool:
    if shutil.which("node") is None:
        return False
    runner = PptxGenCliRunner(Settings(_env_file=None))
    return runner.is_available() and runner.layout_plan_script_path.exists()


@pytest.mark.parametrize("case_id", PPTX_VISUAL_REGRESSION_CASE_IDS)
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

    if candidate_mode_enabled():
        saved = save_screenshot_candidate(case_dir, case=case, screenshot_path=actual)
        pytest.skip(
            f"Wrote review candidate only (did not touch baseline): {saved}. "
            f"Approve with: python scripts/approve_layout_pptx_screenshot_baselines.py "
            f"--case {case_id} --i-reviewed"
        )

    baseline = screenshot_baseline_path(case_dir)
    if not baseline.is_file():
        save_screenshot_candidate(case_dir, case=case, screenshot_path=actual)
        pytest.fail(
            f"{case_id}: missing committed baseline {baseline.name}. "
            f"Candidate written for review. Generate/refresh with "
            f"python scripts/update_layout_pptx_screenshot_baselines.py --case {case_id}, "
            f"then approve with "
            f"scripts/approve_layout_pptx_screenshot_baselines.py --case {case_id} --i-reviewed"
        )

    issues = compare_screenshot_to_baseline(case_dir, actual)
    if issues:
        save_screenshot_candidate(case_dir, case=case, screenshot_path=actual)
        pytest.fail(
            f"{case_id} pptx_visual_regression failed:\n- "
            + "\n- ".join(issues)
            + f"\nCandidate written under {case_dir / 'candidates'} for human review."
        )


def test_screenshot_case_manifests_exist() -> None:
    from tests.golden.visual.composition.screenshot_baseline import load_screenshot_manifest

    missing: list[str] = []
    for case_id in PPTX_VISUAL_REGRESSION_CASE_IDS:
        case_dir = GOLDEN_ROOT / case_id
        baseline = screenshot_baseline_path(case_dir)
        manifest_file = case_dir / "pptx_screenshot_manifest.json"
        if not baseline.is_file() or not manifest_file.is_file():
            missing.append(case_id)
            continue
        manifest = load_screenshot_manifest(case_dir)
        assert manifest.case_id == case_id
        assert manifest.screenshot.file == baseline.name
        assert manifest.font_manifest_hash, f"{case_id} missing font_manifest_hash"
        assert manifest.font_platform, f"{case_id} missing font_platform"
        assert manifest.fonts, f"{case_id} missing fonts[] provenance"

    assert not missing, (
        "Missing committed screenshot baselines for: "
        + ", ".join(missing)
        + ". Use candidate → approve-baseline workflow; do not silent-overwrite."
    )


def test_tracks_are_documented() -> None:
    assert PPTX_MARKER == "pptx_visual_regression"
    assert PPTX_MARKER_LEGACY == "layout_pptx_screenshot"
    assert CANDIDATE_ENV == "ARCHIUM_WRITE_PPTX_SCREENSHOT_CANDIDATES"
