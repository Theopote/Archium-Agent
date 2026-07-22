#!/usr/bin/env python3
"""Promote reviewed PPTX screenshot candidates to committed baselines.

Requires prior candidate generation via
``scripts/update_layout_pptx_screenshot_baselines.py``.

This is the **only** supported way to update ``pptx_screenshot.png`` after a
visual change. Never overwrite baselines from a failing pytest run.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tests.golden.visual.composition.case_builders import (  # noqa: E402
    ICON_EXPANSION_CASE_IDS,
    PPTX_VISUAL_REGRESSION_CASE_IDS,
)
from tests.golden.visual.composition.screenshot_baseline import (  # noqa: E402
    approve_candidate_baseline,
    candidate_screenshot_path,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--case",
        action="append",
        dest="cases",
        required=True,
        help="Case id to approve (repeatable). Refuses --all to force deliberate review.",
    )
    parser.add_argument(
        "--i-reviewed",
        action="store_true",
        required=True,
        help="Confirm you visually reviewed the candidate PNGs",
    )
    args = parser.parse_args(argv)

    known = set(PPTX_VISUAL_REGRESSION_CASE_IDS) | set(ICON_EXPANSION_CASE_IDS)
    golden_root = _PROJECT_ROOT / "tests" / "golden" / "visual" / "composition"
    approved: list[str] = []

    for case_id in args.cases:
        if case_id not in known:
            print(f"ERROR: unknown case id {case_id}", file=sys.stderr)
            return 1
        case_dir = golden_root / case_id
        candidate = candidate_screenshot_path(case_dir)
        if not candidate.is_file():
            print(
                f"ERROR: no candidate for {case_id} at {candidate}. "
                "Generate with scripts/update_layout_pptx_screenshot_baselines.py first.",
                file=sys.stderr,
            )
            return 1
        saved = approve_candidate_baseline(case_dir)
        approved.append(str(saved))

    print(f"Approved {len(approved)} baseline(s). Commit the png + manifest:")
    for path in approved:
        print(f"  - {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
