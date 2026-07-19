#!/usr/bin/env python3
"""Build HTML and JSON summary reports for architectural slide benchmarks."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tests.benchmark.architectural_slides.report_builder import write_benchmark_report  # noqa: E402

DEFAULT_OUTPUT = (
    _PROJECT_ROOT / "tests" / "benchmark" / "architectural_slides" / "reports"
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Directory for benchmark-report.html and benchmark-summary.json",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Regenerate case artifacts before building the report",
    )
    args = parser.parse_args(argv)
    html_path, json_path = write_benchmark_report(args.output_dir, update=args.update)
    print(f"Wrote {html_path}")
    print(f"Wrote {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
