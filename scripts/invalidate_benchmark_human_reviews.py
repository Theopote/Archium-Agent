#!/usr/bin/env python3
"""Invalidate wireframe-based benchmark manual reviews and bootstrap render manifests."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from archium.domain.visual.benchmark import (  # noqa: E402
    DEFAULT_INVALIDATION_REASON_WIREFRAME,
    HumanVisualReview,
    HumanVisualReviewSource,
    ReviewValidity,
)
from tests.benchmark.architectural_slides.artifacts import (  # noqa: E402
    BENCHMARK_ROOT,
    materialized_benchmark_case_ids,
)
from tests.benchmark.architectural_slides.render_manifest import (  # noqa: E402
    bootstrap_case_render_artifacts,
)
from tests.benchmark.architectural_slides.review_paths import (  # noqa: E402
    LEGACY_HUMAN_REVIEW_FILE,
    visual_review_json_path,
)


def invalidate_review(path: Path, *, dry_run: bool) -> bool:
    if not path.is_file():
        return False
    review = HumanVisualReview.model_validate_json(path.read_text(encoding="utf-8"))
    if review.is_invalidated():
        return False
    if review.is_scaffold_review():
        return False
    invalidated = review.model_copy(
        update={
            "source": HumanVisualReviewSource.INVALIDATED,
            "validity": ReviewValidity.INVALID_RENDER_ARTIFACT,
            "review_completed": True,
            "accepted_for_delivery": False,
            "accepted": False,
            "invalidation_reason": DEFAULT_INVALIDATION_REASON_WIREFRAME,
            "reviewer_notes": (
                review.reviewer_notes.strip()
                + "\n[invalidated] wireframe preview is not a valid visual review carrier."
            ).strip(),
        }
    )
    if dry_run:
        return True
    path.write_text(
        json.dumps(invalidated.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=BENCHMARK_ROOT,
        help="Benchmark root directory",
    )
    parser.add_argument("--dry-run", action="store_true", help="Report only; do not write files")
    args = parser.parse_args(argv)

    invalidated = 0
    bootstrapped = 0
    for case_id in materialized_benchmark_case_ids(root=args.root):
        case_dir = args.root / case_id
        review_path = visual_review_json_path(case_dir) or (case_dir / LEGACY_HUMAN_REVIEW_FILE)
        if invalidate_review(review_path, dry_run=args.dry_run):
            invalidated += 1
            print(f"{'would invalidate' if args.dry_run else 'invalidated'} {case_id}")
        bootstrap_case_render_artifacts(case_dir)
        bootstrapped += 1

    if not args.dry_run:
        from archium.application.architectural_benchmark_review_store import (
            regenerate_benchmark_report,
        )

        regenerate_benchmark_report(root=args.root)
        print(f"Regenerated benchmark report at {args.root / 'reports'}")

    print(
        f"Done at {datetime.now(UTC).isoformat()}: "
        f"invalidated={invalidated} bootstrapped={bootstrapped}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
