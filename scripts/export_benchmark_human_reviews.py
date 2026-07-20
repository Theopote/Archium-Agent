#!/usr/bin/env python3
"""Export or import consolidated benchmark manual human-review bundles."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from archium.application.architectural_benchmark_review_store import (  # noqa: E402
    build_human_review_export,
    default_human_review_export_path,
    export_human_review_bundle,
    import_human_review_bundle,
    regenerate_benchmark_report,
)


def _cmd_export(args: argparse.Namespace) -> int:
    output = args.output or default_human_review_export_path()
    path = export_human_review_bundle(
        output,
        include_pending_cases=not args.manual_only,
    )
    bundle = build_human_review_export(include_pending_cases=not args.manual_only)
    print(f"Wrote {path}")
    print(
        f"manual={bundle.manual_review_count}/{bundle.case_count} "
        f"pending={bundle.pending_count} "
        f"gate={'pass' if bundle.human_quality_gate_passed else 'fail'}"
    )
    if bundle.human_quality_gate_reasons:
        for reason in bundle.human_quality_gate_reasons:
            print(f"  - {reason}")
    return 0


def _cmd_import(args: argparse.Namespace) -> int:
    result = import_human_review_bundle(
        args.input,
        skip_existing_manual=args.skip_existing,
    )
    print(
        f"Imported {result.imported_count} review(s); "
        f"skipped {result.skipped_count}; rejected {result.rejected_count}"
    )
    if args.regenerate_report and result.imported_count > 0:
        html_path, json_path = regenerate_benchmark_report()
        print(f"Regenerated {html_path.name} and {json_path.name}")
    return 0 if result.rejected_count == 0 or result.imported_count > 0 else 1


def _cmd_status(_args: argparse.Namespace) -> int:
    bundle = build_human_review_export()
    print(json.dumps(bundle.model_dump(mode="json"), ensure_ascii=False, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    export_parser = sub.add_parser("export", help="Write human_reviews_export.json")
    export_parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output JSON path (default: tests/benchmark/.../reports/human_reviews_export.json)",
    )
    export_parser.add_argument(
        "--manual-only",
        action="store_true",
        help="Omit pending-case queue from export",
    )
    export_parser.set_defaults(func=_cmd_export)

    import_parser = sub.add_parser("import", help="Apply reviews from export JSON")
    import_parser.add_argument("input", type=Path, help="Export bundle or reviews[] JSON")
    import_parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Do not overwrite cases that already have manual reviews",
    )
    import_parser.add_argument(
        "--no-regenerate-report",
        dest="regenerate_report",
        action="store_false",
        help="Skip benchmark-report.html refresh after import",
    )
    import_parser.set_defaults(regenerate_report=True, func=_cmd_import)

    status_parser = sub.add_parser("status", help="Print export bundle JSON to stdout")
    status_parser.set_defaults(func=_cmd_status)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
