#!/usr/bin/env python3
"""Regenerate architectural slide benchmark baselines."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tests.benchmark.architectural_slides.artifacts import UPDATE_ENV  # noqa: E402
from tests.benchmark.architectural_slides.report_builder import write_benchmark_report  # noqa: E402
from tests.benchmark.architectural_slides.runner import run_all_cases  # noqa: E402
from tests.benchmark.architectural_slides.summary_validator import (
    BENCHMARK_REPORTS_DIR,  # noqa: E402
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    os.environ[UPDATE_ENV] = "1"
    summaries = run_all_cases(update=True)
    for summary in summaries:
        print(f"Updated {summary.case_id} -> {summary.case_dir}")
    html_path, json_path = write_benchmark_report(BENCHMARK_REPORTS_DIR, update=False)
    print(f"Wrote {html_path}")
    print(f"Wrote {json_path}")
    print(f"Updated {len(summaries)} benchmark baseline(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
