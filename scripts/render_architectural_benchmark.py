#!/usr/bin/env python3
"""Render all architectural slide benchmark cases and write artifacts."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tests.benchmark.architectural_slides.runner import run_all_cases  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    summaries = run_all_cases(update=True)
    for summary in summaries:
        status = "PASS" if summary.passed else "FAIL"
        print(f"{summary.case_id}: {status} score={summary.layout_score:.3f}")
    failed = [item.case_id for item in summaries if not item.passed]
    if failed:
        print(f"Failed cases: {', '.join(failed)}", file=sys.stderr)
        return 1
    print(f"Rendered {len(summaries)} benchmark case(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
