"""Tests for architectural benchmark human review persistence."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from archium.application.architectural_benchmark_review_store import (
    list_benchmark_cases,
    list_case_review_statuses,
    load_case_layout_review,
    load_case_review,
    review_progress,
    review_progress_by_category,
    save_case_layout_review,
    save_case_review,
)
from archium.domain.visual.benchmark import (
    HumanLayoutReview,
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


def test_list_case_review_statuses_marks_placeholder_pending(tmp_path: Path) -> None:
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
    (case_dir / "human_review.json").write_text(
        json.dumps(
            {
                "case_id": "case_demo",
                "source": "placeholder",
                "information_hierarchy": 4,
                "visual_focus": 4,
                "reading_order": 4,
                "image_text_relationship": 4,
                "whitespace_density": 4,
                "architectural_expression": 4,
                "aesthetic_finish": 4,
                "editability": 4,
                "accepted": False,
                "reviewer_notes": "占位模板",
            }
        ),
        encoding="utf-8",
    )
    statuses = list_case_review_statuses(root=tmp_path)
    assert len(statuses) == 1
    assert statuses[0].pending is True
    assert statuses[0].human_score_label == "待人工评审"


def test_review_progress_by_category_counts_manual_reviews(tmp_path: Path) -> None:
    for index, accepted in enumerate((True, False), start=1):
        case_dir = tmp_path / f"case_{index:03d}"
        case_dir.mkdir()
        (case_dir / "input.json").write_text(
            json.dumps(
                {
                    "case_id": f"case_{index:03d}",
                    "title": f"Case {index}",
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
        (case_dir / "human_review.json").write_text(
            json.dumps(
                {
                    "case_id": f"case_{index:03d}",
                    "source": "manual",
                    "information_hierarchy": 5,
                    "visual_focus": 4,
                    "reading_order": 4,
                    "image_text_relationship": 4,
                    "whitespace_density": 4,
                    "architectural_expression": 4,
                    "aesthetic_finish": 4,
                    "editability": 5,
                    "accepted": accepted,
                    "reviewer": "Reviewer A",
                }
            ),
            encoding="utf-8",
        )

    breakdown = review_progress_by_category(root=tmp_path)
    assert breakdown["drawing"]["case_count"] == 2
    assert breakdown["drawing"]["manual_review_count"] == 2
    assert breakdown["drawing"]["manual_accepted_count"] == 1


def test_regenerate_benchmark_report_uses_disk_only_summary(tmp_path: Path) -> None:
    from archium.application.architectural_benchmark_review_store import regenerate_benchmark_report

    case_dir = tmp_path / "case_001_site_plan"
    case_dir.mkdir()
    (case_dir / "input.json").write_text(
        json.dumps(
            {
                "case_id": "case_001_site_plan",
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
    (case_dir / "score_baseline.json").write_text(
        json.dumps({"score": 0.95, "valid": True, "has_critical": False}),
        encoding="utf-8",
    )
    (case_dir / "human_review.json").write_text(
        json.dumps(
            {
                "case_id": "case_001_site_plan",
                "source": "placeholder",
                "information_hierarchy": 4,
                "visual_focus": 4,
                "reading_order": 4,
                "image_text_relationship": 4,
                "whitespace_density": 4,
                "architectural_expression": 4,
                "aesthetic_finish": 4,
                "editability": 4,
                "accepted": False,
            }
        ),
        encoding="utf-8",
    )

    html_path, json_path = regenerate_benchmark_report(root=tmp_path)
    assert html_path.is_file()
    assert json_path.is_file()
    summary = json.loads(json_path.read_text(encoding="utf-8"))
    assert summary["case_count"] == 1


def _seed_visual_review_ready(case_dir: Path) -> None:
    from archium.domain.visual.benchmark import BenchmarkRenderManifest
    from tests.benchmark.architectural_slides.render_manifest import write_render_manifest

    (case_dir / "final_render.png").write_bytes(b"png")
    write_render_manifest(
        case_dir,
        BenchmarkRenderManifest(
            render_source="pptx_screenshot",
            render_valid=True,
            asset_count=1,
            real_asset_count=1,
            placeholder_asset_count=0,
            rendered_at=datetime.now(UTC),
            renderer="test",
        ),
    )


def test_save_case_review_blocked_without_final_render(tmp_path: Path) -> None:
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
    )
    with pytest.raises(WorkflowError, match="final_render"):
        save_case_review(review, root=tmp_path)


def test_save_case_layout_review_round_trip(tmp_path: Path) -> None:
    case_dir = tmp_path / "case_demo"
    case_dir.mkdir()
    (case_dir / "wireframe.png").write_bytes(b"png")
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
    review = HumanLayoutReview(
        case_id="case_demo",
        source=HumanVisualReviewSource.MANUAL,
        information_hierarchy=5,
        reading_order=4,
        whitespace_density=4,
        spatial_balance=4,
        layout_clarity=5,
        accepted_for_geometry=True,
        reviewer="Reviewer A",
        reviewed_at=datetime.now(UTC),
    )
    path = save_case_layout_review(review, root=tmp_path)
    loaded = load_case_layout_review("case_demo", root=tmp_path)
    assert path.name == "human_layout_review.json"
    assert loaded is not None
    assert loaded.accepted_for_geometry is True


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
    _seed_visual_review_ready(case_dir)
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
