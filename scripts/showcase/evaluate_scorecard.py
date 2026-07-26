"""Evaluate a filled Showcase investor scorecard against the stage gate."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from archium.domain.visual.showcase_score import (  # noqa: E402
    showcase_score_from_dict,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate Showcase investor scorecard")
    parser.add_argument("scorecard", type=Path, help="Path to filled scorecard JSON")
    args = parser.parse_args(argv)

    raw = json.loads(args.scorecard.read_text(encoding="utf-8"))
    # Template may include helper keys; keep only model fields.
    payload = {
        key: raw[key]
        for key in (
            "case_id",
            "schema_version",
            "style_preset_id",
            "dimensions",
            "notes",
            "reviewer",
            "demo_tour_ok",
        )
        if key in raw
    }
    score = showcase_score_from_dict(payload)
    gate = score.evaluate_gate()
    print(
        json.dumps(
            {
                "case_id": score.case_id,
                "total": gate.total,
                "passed": gate.passed,
                "complete": gate.complete,
                "failures": gate.failures,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if gate.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
