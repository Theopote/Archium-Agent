#!/usr/bin/env python3
"""Materialize pptx_render.png for Phase 9 benchmark visual review eligibility."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tests.benchmark.architectural_slides.artifacts import (  # noqa: E402
    BENCHMARK_ROOT,
    materialized_benchmark_case_ids,
)
from tests.benchmark.architectural_slides.phase9_pptx_render import (  # noqa: E402
    materialize_case_pptx_render,
    write_phase9_eligibility_report,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=BENCHMARK_ROOT)
    parser.add_argument("--case", action="append", dest="case_ids")
    parser.add_argument("--force", action="store_true", help="Re-rasterize even if pptx_render exists")
    args = parser.parse_args(argv)

    case_ids = tuple(args.case_ids) if args.case_ids else materialized_benchmark_case_ids(root=args.root)
    results = []
    for case_id in case_ids:
        result = materialize_case_pptx_render(args.root / case_id, force=args.force)
        results.append(result)
        flag = "OK" if result.succeeded else "FAIL"
        print(f"{flag} {result.case_id}: {result.notes}")

    report = write_phase9_eligibility_report(args.root, results=results)
    ok = sum(1 for item in results if item.succeeded)
    print(f"Done: {ok}/{len(results)} pptx_render materialized; eligibility report → {report}")
    return 0 if ok == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
