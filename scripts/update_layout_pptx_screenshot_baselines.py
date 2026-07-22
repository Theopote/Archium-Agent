#!/usr/bin/env python3
"""Generate PPTX screenshot *candidates* for human review (never overwrites baselines).

Workflow:
  1. Run this script → writes ``candidates/pptx_screenshot.candidate.png``
  2. Upload / open candidates (CI artifact or local)
  3. Human review
  4. ``python scripts/approve_layout_pptx_screenshot_baselines.py --case …``

Do **not** commit candidates. Do **not** bulk-overwrite baselines from a failing test.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from archium.application.visual.visual_intent_service import VisualIntentService  # noqa: E402
from archium.infrastructure.renderers.pptx_screenshot import (  # noqa: E402
    screenshot_tools_available,
)
from tests.golden.visual.composition.case_builders import (  # noqa: E402
    ICON_EXPANSION_CASE_IDS,
    PPTX_VISUAL_REGRESSION_CASE_IDS,
    SCREENSHOT_CASE_IDS,
    build_composition_case,
)
from tests.golden.visual.composition.screenshot_baseline import (  # noqa: E402
    CANDIDATE_ENV,
    render_case_pptx_screenshot,
    save_screenshot_candidate,
)
from tests.golden.visual.composition.visual_regression_tracks import (  # noqa: E402
    CANDIDATE_DIRNAME,
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
        help="Case id (default: all CI-gated pptx_visual_regression cases)",
    )
    parser.add_argument(
        "--include-expansion",
        action="store_true",
        help="Also generate candidates for icon expansion cases (V10–V18)",
    )
    args = parser.parse_args(argv)

    if args.cases:
        case_ids = tuple(args.cases)
    elif args.include_expansion:
        case_ids = tuple(
            dict.fromkeys([*PPTX_VISUAL_REGRESSION_CASE_IDS, *ICON_EXPANSION_CASE_IDS])
        )
    else:
        case_ids = SCREENSHOT_CASE_IDS

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
    written: list[str] = []

    for case_id in case_ids:
        case = build_composition_case(case_id, intent_service)
        with tempfile.TemporaryDirectory(prefix=f"archium_candidate_{case_id}_") as tmp:
            work_dir = Path(tmp)
            screenshot = render_case_pptx_screenshot(case, work_dir)
            if screenshot is None:
                print(f"ERROR: failed to render screenshot for {case_id}", file=sys.stderr)
                return 1
            out_dir = golden_root / case_id
            saved = save_screenshot_candidate(out_dir, case=case, screenshot_path=screenshot)
            written.append(str(saved))

    print(
        f"Wrote {len(written)} candidate screenshot(s) under */{CANDIDATE_DIRNAME}/ "
        f"(env {CANDIDATE_ENV}=1 is for pytest candidate mode).\n"
        "Next: review PNGs, then run scripts/approve_layout_pptx_screenshot_baselines.py"
    )
    for path in written:
        print(f"  - {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
