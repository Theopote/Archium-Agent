"""Bootstrap Phase 4 benchmark artifacts (editability, layout_score, review validity)."""

from __future__ import annotations

import json
from pathlib import Path

from archium.domain.visual.benchmark import HumanVisualReview, HumanVisualReviewSource, ReviewValidity
from tests.benchmark.architectural_slides.artifacts import (
    case_dir,
    default_editability_review,
    materialized_benchmark_case_ids,
)


def main() -> None:
    for case_id in materialized_benchmark_case_ids():
        directory = case_dir(case_id)
        human_path = directory / "human_review.json"
        if human_path.is_file():
            review = HumanVisualReview.model_validate_json(human_path.read_text(encoding="utf-8"))
            if review.source == HumanVisualReviewSource.INVALIDATED or review.is_invalidated():
                review = review.model_copy(
                    update={
                        "validity": ReviewValidity.INVALID_RENDER_ARTIFACT,
                        "review_completed": True,
                        "accepted_for_delivery": False,
                        "accepted": False,
                    }
                )
                human_path.write_text(
                    json.dumps(review.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
        editability_path = directory / "editability_review.json"
        if not editability_path.is_file():
            editability_path.write_text(
                json.dumps(
                    default_editability_review(case_id).model_dump(mode="json"),
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
        layout_score_path = directory / "layout_score.json"
        baseline_path = directory / "score_baseline.json"
        if not layout_score_path.is_file() and baseline_path.is_file():
            baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
            payload = {
                "benchmark": "layout_geometry",
                "case_id": case_id,
                "layout_score": baseline.get("score"),
                "layout_valid": baseline.get("valid"),
                "has_critical": baseline.get("has_critical"),
                "passed": bool(baseline.get("valid")) and not baseline.get("has_critical"),
            }
            layout_score_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
    print(f"bootstrapped {len(materialized_benchmark_case_ids())} cases")


if __name__ == "__main__":
    main()
