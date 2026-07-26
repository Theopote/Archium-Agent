"""CI-safe Showcase Case 001 smoke (no LLM, no PPTX)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow `python scripts/showcase/run_case_001_smoke.py` from repo root.
_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from archium.application.visual.showcase_case_001 import (  # noqa: E402
    CASE_001_ID,
    DEMO_TOUR_TITLES,
    assert_case_001_rhythm,
    load_case_001_manifest,
    load_case_001_outline,
    plan_case_001_composition,
    scorecard_template,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Showcase Case 001 CI smoke")
    parser.add_argument(
        "--write-scorecard",
        action="store_true",
        help="Refresh scorecard.template.json from domain defaults",
    )
    args = parser.parse_args(argv)

    manifest = load_case_001_manifest()
    outline = load_case_001_outline()
    assert manifest["case_id"] == CASE_001_ID
    assert len(outline) == 20

    plan = plan_case_001_composition(outline=outline)
    snapshot = assert_case_001_rhythm(plan)

    titles = [str(row["title"]) for row in outline]
    for tour_title in DEMO_TOUR_TITLES:
        if tour_title not in titles:
            raise SystemExit(f"demo tour title missing from outline: {tour_title}")

    if args.write_scorecard:
        target = (
            Path(__file__).resolve().parent
            / "case_001_hospital"
            / "scorecard.template.json"
        )
        target.write_text(
            json.dumps(scorecard_template(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"wrote {target}")

    print(json.dumps({"ok": True, "snapshot": snapshot}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
