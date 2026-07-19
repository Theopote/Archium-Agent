"""Load and save manual human reviews for architectural slide benchmarks."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from archium.domain.visual.benchmark import (
    HUMAN_REVIEW_PENDING_LABEL,
    HumanVisualReview,
    HumanVisualReviewSource,
)
from archium.exceptions import WorkflowError

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BENCHMARK_ROOT = (
    _PROJECT_ROOT / "tests" / "benchmark" / "architectural_slides"
)
DEFAULT_REPORTS_DIR = DEFAULT_BENCHMARK_ROOT / "reports"


@dataclass(frozen=True)
class BenchmarkCaseSummary:
    """Minimal metadata for one benchmark case directory."""

    case_id: str
    title: str
    page_type: str
    category: str
    layout_family: str
    layout_variant: str
    preview_path: Path
    human_review_path: Path
    layout_score: float | None
    rule_passed: bool | None


@dataclass(frozen=True)
class CaseReviewStatus:
    """Review status row for one benchmark case."""

    case_id: str
    title: str
    category: str
    page_type: str
    rule_passed: bool | None
    human_score_label: str
    passes_threshold: bool | None
    accepted_for_delivery: bool
    reviewer: str | None
    pending: bool


def list_case_review_statuses(*, root: Path | None = None) -> list[CaseReviewStatus]:
    statuses: list[CaseReviewStatus] = []
    for case in list_benchmark_cases(root=root):
        review = load_case_review(case.case_id, root=root)
        pending = review is None or review.is_scaffold_review()
        if pending:
            statuses.append(
                CaseReviewStatus(
                    case_id=case.case_id,
                    title=case.title,
                    category=case.category,
                    page_type=case.page_type,
                    rule_passed=case.rule_passed,
                    human_score_label=HUMAN_REVIEW_PENDING_LABEL,
                    passes_threshold=None,
                    accepted_for_delivery=False,
                    reviewer=None,
                    pending=True,
                )
            )
            continue
        assert review is not None
        statuses.append(
            CaseReviewStatus(
                case_id=case.case_id,
                title=case.title,
                category=case.category,
                page_type=case.page_type,
                rule_passed=case.rule_passed,
                human_score_label=review.human_score_label(),
                passes_threshold=review.passes_threshold(),
                accepted_for_delivery=bool(review.accepted),
                reviewer=review.reviewer or None,
                pending=False,
            )
        )
    return statuses


def benchmark_report_paths(*, root: Path | None = None) -> tuple[Path, Path]:
    reports_dir = benchmark_root(root) / "reports"
    return reports_dir / "benchmark-report.html", reports_dir / "benchmark-summary.json"


def review_progress_by_category(*, root: Path | None = None) -> dict[str, dict[str, int]]:
    by_category: dict[str, dict[str, int]] = {}
    for status in list_case_review_statuses(root=root):
        bucket = by_category.setdefault(
            status.category,
            {"case_count": 0, "manual_review_count": 0, "manual_accepted_count": 0},
        )
        bucket["case_count"] += 1
        if not status.pending:
            bucket["manual_review_count"] += 1
        if status.accepted_for_delivery:
            bucket["manual_accepted_count"] += 1
    return by_category


def benchmark_root(root: Path | None = None) -> Path:
    return root or DEFAULT_BENCHMARK_ROOT


def list_benchmark_cases(*, root: Path | None = None) -> list[BenchmarkCaseSummary]:
    base = benchmark_root(root)
    summaries: list[BenchmarkCaseSummary] = []
    for directory in sorted(base.glob("case_*")):
        if not directory.is_dir():
            continue
        input_path = directory / "input.json"
        if not input_path.is_file():
            continue
        payload = json.loads(input_path.read_text(encoding="utf-8"))
        score_payload = _read_optional_json(directory / "score_baseline.json")
        layout_score = None
        rule_passed = None
        if score_payload is not None:
            raw_score = score_payload.get("score")
            layout_score = float(raw_score) if isinstance(raw_score, (int, float)) else None
            valid = score_payload.get("valid")
            has_critical = score_payload.get("has_critical")
            if isinstance(valid, bool) and isinstance(has_critical, bool):
                rule_passed = valid and not has_critical
        summaries.append(
            BenchmarkCaseSummary(
                case_id=str(payload["case_id"]),
                title=str(payload["title"]),
                page_type=str(payload["page_type"]),
                category=str(payload["category"]),
                layout_family=str(payload["expected_layout_family"]),
                layout_variant=str(payload["layout_variant"]),
                preview_path=directory / "preview.png",
                human_review_path=directory / "human_review.json",
                layout_score=layout_score,
                rule_passed=rule_passed,
            )
        )
    return summaries


def load_case_review(case_id: str, *, root: Path | None = None) -> HumanVisualReview | None:
    path = benchmark_root(root) / case_id / "human_review.json"
    if not path.is_file():
        return None
    return HumanVisualReview.model_validate(
        json.loads(path.read_text(encoding="utf-8"))
    )


def save_case_review(
    review: HumanVisualReview,
    *,
    root: Path | None = None,
) -> Path:
    if review.source != HumanVisualReviewSource.MANUAL:
        msg = "Benchmark human reviews saved from the UI must use source=manual"
        raise ValueError(msg)
    if not review.reviewer.strip():
        raise WorkflowError("请填写评审人姓名后再保存人工评审。")
    if review.reviewed_at is None:
        review = review.model_copy(update={"reviewed_at": datetime.now(UTC)})
    path = benchmark_root(root) / review.case_id / "human_review.json"
    if not path.parent.is_dir():
        msg = f"Unknown benchmark case directory: {review.case_id}"
        raise ValueError(msg)
    path.write_text(
        json.dumps(review.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def review_progress(*, root: Path | None = None) -> dict[str, int]:
    cases = list_benchmark_cases(root=root)
    manual_accepted = 0
    manual_total = 0
    placeholder = 0
    for case in cases:
        review = load_case_review(case.case_id, root=root)
        if review is None:
            placeholder += 1
            continue
        if review.is_scaffold_review():
            placeholder += 1
            continue
        manual_total += 1
        if review.accepted:
            manual_accepted += 1
    return {
        "case_count": len(cases),
        "manual_review_count": manual_total,
        "manual_accepted_count": manual_accepted,
        "placeholder_count": placeholder,
    }


def regenerate_benchmark_report(*, root: Path | None = None) -> tuple[Path, Path]:
    from tests.benchmark.architectural_slides.report_builder import write_benchmark_report

    base = benchmark_root(root)
    return write_benchmark_report(base / "reports", update=False)


def _read_optional_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None
