#!/usr/bin/env python3
"""Compile architectural benchmark visuals with explicit write modes.

CI must use ``--materialize-ci-samples`` (ephemeral checkout / sample smoke).
Committed Golden updates require ``--approve-goldens`` after human review.
"""

from __future__ import annotations

import argparse
import os
import sys
import warnings
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tests.benchmark.architectural_slides.artifacts import (  # noqa: E402
    BENCHMARK_ROOT,
    UPDATE_ENV,
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
        "--output-dir",
        type=Path,
        default=None,
        help=(
            "Optional alternate root for writes (CI samples). "
            "When set, cases are written under this directory instead of --root."
        ),
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
    write_mode = parser.add_mutually_exclusive_group()
    write_mode.add_argument(
        "--materialize-ci-samples",
        action="store_true",
        help=(
            "Allow writing sample renders for CI pipeline smoke "
            "(ephemeral workspace; does not mean baseline approval)."
        ),
    )
    write_mode.add_argument(
        "--approve-goldens",
        action="store_true",
        help=(
            "Permit writing into the committed architectural_slides case tree "
            f"after human review. Also accepted via {UPDATE_ENV}=1."
        ),
    )
    write_mode.add_argument(
        "--write-goldens",
        action="store_true",
        help=argparse.SUPPRESS,  # deprecated alias for --approve-goldens
    )
    args = parser.parse_args(argv)

    if args.write_goldens:
        warnings.warn(
            "--write-goldens is deprecated; use --approve-goldens for committed "
            "baselines, or --materialize-ci-samples for CI ephemeral samples.",
            DeprecationWarning,
            stacklevel=1,
        )
        args.approve_goldens = True

    write_root = (args.output_dir or args.root).resolve()
    source_root = args.root.resolve()
    writing_committed_tree = (
        write_root == BENCHMARK_ROOT.resolve() and not args.dry_run
    )
    allowed = (
        args.approve_goldens
        or args.materialize_ci_samples
        or os.environ.get(UPDATE_ENV) == "1"
    )
    if writing_committed_tree and not allowed:
        print(
            "Refusing to overwrite committed Golden binaries under "
            f"{BENCHMARK_ROOT}.\n"
            "CI samples: re-run with --materialize-ci-samples "
            "(optionally --output-dir $RUNNER_TEMP/...).\n"
            "Committed baselines: re-run with --approve-goldens after review, "
            f"or set {UPDATE_ENV}=1.\n"
            "See tests/benchmark/architectural_slides/README.md.",
            file=sys.stderr,
        )
        return 2
    if writing_committed_tree and args.materialize_ci_samples and not args.approve_goldens:
        # CI checkouts are ephemeral; allow materialize against the tree in Actions.
        pass

    case_ids = (
        tuple(args.case_ids)
        if args.case_ids
        else materialized_benchmark_case_ids(root=source_root)
    )
    rendered = 0
    pptx_only = 0
    skipped = 0

    for case_id in case_ids:
        case_dir = write_root / case_id
        if args.dry_run:
            print(f"would render {case_id} -> {case_dir}")
            continue
        case_dir.mkdir(parents=True, exist_ok=True)
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

    if not args.dry_run and rendered > 0 and write_root == BENCHMARK_ROOT.resolve():
        from archium.application.architectural_benchmark_review_store import (
            regenerate_benchmark_report,
        )

        regenerate_benchmark_report(root=write_root)

    print(
        f"Done: final_render={rendered} pptx_only={pptx_only} skipped={skipped} "
        f"total={len(case_ids)} write_root={write_root}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
