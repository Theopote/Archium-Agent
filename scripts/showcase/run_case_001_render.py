"""Render Showcase Case 001: LayoutSolver → layout JSON / optional PPTX."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from archium.application.visual.showcase_case_001 import (  # noqa: E402
    CASE_001_DEFAULT_PRESET,
    build_case_001_render_bundle,
    case_001_outputs_dir,
    export_case_001_pptx,
    write_case_001_dry_run,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Showcase Case 001 render: outline → LayoutPlans → "
            "layout instructions (and optional presentation.pptx)."
        )
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Write layout_plans + instruction deck only (no Node/PPTX).",
    )
    parser.add_argument(
        "--style-preset",
        default=CASE_001_DEFAULT_PRESET,
        help=f"Style preset id (default: {CASE_001_DEFAULT_PRESET})",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Override outputs directory (default: case pack outputs/).",
    )
    args = parser.parse_args(argv)

    out = args.output_dir or case_001_outputs_dir()
    bundle = build_case_001_render_bundle(style_preset_id=args.style_preset)

    if args.dry_run:
        summary = write_case_001_dry_run(bundle, output_dir=out)
    else:
        summary = export_case_001_pptx(bundle, output_dir=out)

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if summary.get("mode") == "dry_run_only":
        return 0
    if not args.dry_run and summary.get("pptx_path") is None:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
