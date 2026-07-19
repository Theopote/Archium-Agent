"""Tests for architectural benchmark human review persistence."""

from __future__ import annotations

import json
from pathlib import Path

from datetime import UTC, datetime

import pytest
from archium.application.architectural_benchmark_review_store import (
    list_benchmark_cases,
    load_case_review,
    review_progress,
    save_case_review,
)
from archium.domain.visual.benchmark import (
    HumanVisualReview,
    HumanVisualReviewSource,
)
from archium.exceptions import WorkflowError


def test_list_benchmark_cases_includes_thirty_cases() -> None:
    cases = list_benchmark_cases()
    assert len(cases) == 30
    assert cases[0].case_id.startswith("case_")


def test_save_case_review_requires_manual_source(tmp_path: Path) -> None:
    case_dir = tmp_path / "case_demo"
    case_dir.mkdir()
    (case_dir / "input.json").write_text(
        json.dumps(
            {
                "case_id": "case_demo",
                "title": "Demo",
                "category": "drawing",
                "page_type": "demo",
                "page_task": "demo",
                "visual_focus": "demo",
                "expected_layout_family": "drawing_focus",
                "allowed_layout_variants": ["drawing_only"],
                "layout_variant": "drawing_only",
            }
        ),
        encoding="utf-8",
    )
    review = HumanVisualReview(
        case_id="case_demo",
        source=HumanVisualReviewSource.PLACEHOLDER,
        information_hierarchy=4,
        visual_focus=4,
        reading_order=4,
        image_text_relationship=4,
        whitespace_density=4,
        architectural_expression=4,
        aesthetic_finish=4,
        editability=4,
        accepted=False,
    )
    with pytest.raises(ValueError, match="source=manual"):
        save_case_review(review, root=tmp_path)


def test_save_case_review_requires_reviewer_name(tmp_path: Path) -> None:
    case_dir = tmp_path / "case_demo"
    case_dir.mkdir()
    (case_dir / "input.json").write_text(
        json.dumps(
            {
                "case_id": "case_demo",
                "title": "Demo",
                "category": "drawing",
                "page_type": "demo",
                "page_task": "demo",
                "visual_focus": "demo",
                "expected_layout_family": "drawing_focus",
                "allowed_layout_variants": ["drawing_only"],
                "layout_variant": "drawing_only",
            }
        ),
        encoding="utf-8",
    )
    review = HumanVisualReview(
        case_id="case_demo",
        source=HumanVisualReviewSource.MANUAL,
        information_hierarchy=5,
        visual_focus=4,
        reading_order=4,
        image_text_relationship=4,
        whitespace_density=4,
        architectural_expression=4,
        aesthetic_finish=4,
        editability=5,
        accepted=True,
    )
    with pytest.raises(WorkflowError, match="评审人"):
        save_case_review(review, root=tmp_path)


def test_save_and_load_manual_review_round_trip(tmp_path: Path) -> None:
    case_dir = tmp_path / "case_demo"
    case_dir.mkdir()
    (case_dir / "input.json").write_text(
        json.dumps(
            {
                "case_id": "case_demo",
                "title": "Demo",
                "category": "drawing",
                "page_type": "demo",
                "page_task": "demo",
                "visual_focus": "demo",
                "expected_layout_family": "drawing_focus",
                "allowed_layout_variants": ["drawing_only"],
                "layout_variant": "drawing_only",
            }
        ),
        encoding="utf-8",
    )
    review = HumanVisualReview(
        case_id="case_demo",
        source=HumanVisualReviewSource.MANUAL,
        information_hierarchy=5,
        visual_focus=4,
        reading_order=4,
        image_text_relationship=4,
        whitespace_density=4,
        architectural_expression=4,
        aesthetic_finish=4,
        editability=5,
        accepted=True,
        reviewer="Reviewer A",
        reviewed_at=datetime.now(UTC),
        reviewer_notes="Manual review complete.",
    )
    path = save_case_review(review, root=tmp_path)
    assert path.is_file()
    loaded = load_case_review("case_demo", root=tmp_path)
    assert loaded is not None
    assert loaded.source == HumanVisualReviewSource.MANUAL
    assert loaded.accepted is True
    progress = review_progress(root=tmp_path)
    assert progress["manual_accepted_count"] == 1
