#!/usr/bin/env python3
"""Seed the Visual QA calibration corpus with synthetic labeled samples."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from archium.application.visual_qa_corpus_service import VisualQACorpusService  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="Optional manifest path override",
    )
    parser.add_argument(
        "--calibrate",
        action="store_true",
        help="Run calibration after seeding",
    )
    parser.add_argument(
        "--overwrite-images",
        action="store_true",
        help="Regenerate PNG files even if they already exist",
    )
    args = parser.parse_args()

    service = (
        VisualQACorpusService(manifest_path=args.manifest)
        if args.manifest
        else VisualQACorpusService()
    )
    result = service.seed_synthetic_corpus(
        overwrite_images=args.overwrite_images,
        replace_manifest=True,
    )
    progress = result["progress"]
    print(
        f"Seeded {result['generated_count']} samples "
        f"({progress['total_current']}/{progress['total_target']})."
    )

    if args.calibrate:
        report = service.calibrate()
        print(f"Calibration report written to {service.report_path}")
        checks = report.get("checks", {})
        for rule_code, payload in sorted(checks.items()):
            score = payload.get("precision") or payload.get("drawing_type_accuracy")
            meets = payload.get("meets_target")
            status = "PASS" if meets else ("FAIL" if meets is False else "N/A")
            score_text = f"{score:.2%}" if isinstance(score, (int, float)) else "n/a"
            print(f"  {rule_code}: {score_text} [{status}]")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
