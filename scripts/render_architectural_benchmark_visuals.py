#!/usr/bin/env python3
"""Re-export full-content PPTX and final_render.png for architectural benchmark cases."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tests.benchmark.architectural_slides.artifacts import (  # noqa: E402
    BENCHMARK_ROOT,
    ensure_case_assets,
    materialized_benchmark_case_ids,
)
from tests.benchmark.architectural_slides.case_builders import build_benchmark_case  # noqa: E402
from tests.benchmark.architectural_slides.render_manifest import (  # noqa: E402
    final_render_path,
)
from tests.benchmark.architectural_slides.render_pipeline import (  # noqa: E402
    render_benchmark_visual_artifacts,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=BENCHMARK_ROOT,
        help="Benchmark root directory",
    )
    parser.add_argument(
        "--case",
        action="append",
        dest="case_ids",
        help="Limit to specific case_id (repeatable)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List cases only; do not write artifacts",
    )
    args = parser.parse_args(argv)

    case_ids = tuple(args.case_ids) if args.case_ids else materialized_benchmark_case_ids(root=args.root)
    rendered = 0
    pptx_only = 0
    skipped = 0

    for case_id in case_ids:
        case_dir = args.root / case_id
        if args.dry_run:
            print(f"would render {case_id}")
            continue
        result = build_benchmark_case(case_id)
        ensure_case_assets(case_id, case_dir / "assets")
        manifest = render_benchmark_visual_artifacts(result, case_dir)
        if manifest.render_valid:
            rendered += 1
            print(f"OK {case_id} -> {final_render_path(case_dir)}")
        elif (case_dir / manifest.pptx_path).is_file():
            pptx_only += 1
            print(f"PPTX {case_id} (no final_render; {manifest.notes[:80]}…)")
        else:
            skipped += 1
            print(f"SKIP {case_id} ({manifest.notes[:80]}…)")

    if not args.dry_run and rendered > 0:
        from archium.application.architectural_benchmark_review_store import (
            regenerate_benchmark_report,
        )

        regenerate_benchmark_report(root=args.root)

    print(
        f"Done: final_render={rendered} pptx_only={pptx_only} skipped={skipped} "
        f"total={len(case_ids)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
