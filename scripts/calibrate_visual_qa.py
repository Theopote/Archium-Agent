#!/usr/bin/env python3
"""Run Visual QA calibration against the labeled corpus and write a report."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from archium.application.visual_qa_calibration import (  # noqa: E402
    DEFAULT_MANIFEST_PATH,
    DEFAULT_REPORT_PATH,
    run_calibration,
    write_calibration_report,
)


def _print_summary(report: dict[str, object]) -> None:
    progress = report["corpus_progress"]  # type: ignore[index]
    print("Visual QA Calibration Report")
    print("=" * 40)
    print(f"Analyzer version: {report['analyzer_version']}")
    print(
        f"Corpus progress: {progress['total_current']}/{progress['total_target']} images labeled"
    )
    missing = report.get("missing_files", [])
    if missing:
        print(f"Missing image files: {len(missing)}")

    print("\nCheck metrics:")
    checks = report["checks"]  # type: ignore[index]
    for rule_code, payload in sorted(checks.items()):
        score = payload.get("precision") or payload.get("drawing_type_accuracy")
        target = payload.get("target_precision")
        meets = payload.get("meets_target")
        status = "PASS" if meets else ("FAIL" if meets is False else "N/A")
        score_text = f"{score:.2%}" if isinstance(score, (int, float)) else "n/a"
        target_text = f"{target:.0%}" if isinstance(target, (int, float)) else "n/a"
        print(
            f"  {rule_code}: score={score_text} target={target_text} "
            f"[{status}] evaluated={payload.get('evaluated', payload.get('drawing_type_total', 0))}"
        )

    print("\nFormal emit eligible rule codes:")
    for rule_code in report.get("formal_emit_eligible_rule_codes", []):
        print(f"  - {rule_code}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST_PATH,
        help="Path to labeled corpus manifest JSON",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_REPORT_PATH,
        help="Where to write calibration_report.json",
    )
    args = parser.parse_args()

    manifest_path = args.manifest if args.manifest.is_absolute() else PROJECT_ROOT / args.manifest
    output_path = args.output if args.output.is_absolute() else PROJECT_ROOT / args.output

    report = run_calibration(manifest_path)
    write_calibration_report(report, output_path)
    _print_summary(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
