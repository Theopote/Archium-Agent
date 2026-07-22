#!/usr/bin/env python3
"""Regenerate LayoutPlan PPTX screenshot baselines for composition golden cases."""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from archium.application.visual.visual_intent_service import VisualIntentService  # noqa: E402
from archium.infrastructure.renderers.pptx_screenshot import (
    screenshot_tools_available,  # noqa: E402
)
from tests.golden.visual.composition.case_builders import (  # noqa: E402
    SCREENSHOT_CASE_IDS,
    build_composition_case,
)
from tests.golden.visual.composition.screenshot_baseline import (  # noqa: E402
    UPDATE_ENV,
    render_case_pptx_screenshot,
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


def _intent_service() -> VisualIntentService:
    service = VisualIntentService.__new__(VisualIntentService)
    service._session = None  # noqa: SLF001
    service._llm = None  # noqa: SLF001
    service._intents = _FakeIntentRepo()  # noqa: SLF001
    return service


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--case",
        action="append",
        dest="cases",
        help="Case id to refresh (default: all screenshot cases)",
    )
    args = parser.parse_args(argv)
    case_ids = tuple(args.cases or SCREENSHOT_CASE_IDS)

    if not screenshot_tools_available():
        print(
            "ERROR: PPTX screenshot tools unavailable.\n"
            "  Linux/CI: sudo apt-get install -y libreoffice poppler-utils\n"
            "  macOS: brew install libreoffice poppler\n"
            "  Windows: install Microsoft PowerPoint (COM) or LibreOffice + Poppler",
            file=sys.stderr,
        )
        return 1

    golden_root = _PROJECT_ROOT / "tests" / "golden" / "visual" / "composition"
    intent_service = _intent_service()
    updated: list[str] = []

    for case_id in case_ids:
        case = build_composition_case(case_id, intent_service)
        with tempfile.TemporaryDirectory(prefix=f"archium_screenshot_{case_id}_") as tmp:
            work_dir = Path(tmp)
            screenshot = render_case_pptx_screenshot(case, work_dir)
            if screenshot is None:
                print(f"ERROR: failed to render screenshot for {case_id}", file=sys.stderr)
                return 1
            out_dir = golden_root / case_id
            saved = save_screenshot_baseline(out_dir, case=case, screenshot_path=screenshot)
            updated.append(str(saved))

    print(f"Updated {len(updated)} screenshot baseline(s) via {UPDATE_ENV}=1 workflow:")
    for path in updated:
        print(f"  - {path}")
    print("Commit pptx_screenshot.png and pptx_screenshot_manifest.json under each case directory.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
