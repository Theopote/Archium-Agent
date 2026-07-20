"""Load and save manual human reviews for architectural slide benchmarks."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from archium.application.human_review_gate import evaluate_benchmark_human_gate
from archium.domain.visual.benchmark import (
    BENCHMARK_VISUAL_REVIEW_REQUIRES_FINAL_RENDER,
    HUMAN_REVIEW_INVALIDATED_LABEL,
    HUMAN_REVIEW_PENDING_LABEL,
    BenchmarkHumanReviewExport,
    BenchmarkPendingCase,
    EditabilityReview,
    HumanLayoutReview,
    HumanVisualReview,
    HumanVisualReviewSource,
)
from archium.exceptions import WorkflowError

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BENCHMARK_ROOT = (
    _PROJECT_ROOT / "tests" / "benchmark" / "architectural_slides"
)
DEFAULT_REPORTS_DIR = DEFAULT_BENCHMARK_ROOT / "reports"
HUMAN_VISUAL_REVIEW_FILE = "human_visual_review.json"
HUMAN_LAYOUT_REVIEW_FILE = "human_layout_review.json"
EDITABILITY_REVIEW_FILE = "editability_review.json"
LEGACY_HUMAN_REVIEW_FILE = "human_review.json"


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
    wireframe_path: Path
    scene_preview_path: Path
    pptx_render_path: Path
    final_render_path: Path
    human_review_path: Path
    layout_review_path: Path
    editability_review_path: Path
    layout_score: float | None
    rule_passed: bool | None


@dataclass(frozen=True)
class HumanReviewImportResult:
    """Outcome of importing a benchmark human-review export bundle."""

    imported_count: int
    skipped_count: int
    rejected_count: int
    paths: list[Path]


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
        pending = (
            review is None
            or review.is_scaffold_review()
            or review.is_invalidated()
        )
        if pending:
            label = HUMAN_REVIEW_PENDING_LABEL
            if review is not None and review.is_invalidated():
                label = HUMAN_REVIEW_INVALIDATED_LABEL
            statuses.append(
                CaseReviewStatus(
                    case_id=case.case_id,
                    title=case.title,
                    category=case.category,
                    page_type=case.page_type,
                    rule_passed=case.rule_passed,
                    human_score_label=label,
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
                accepted_for_delivery=bool(review.accepted_for_delivery),
                reviewer=review.reviewer or None,
                pending=False,
            )
        )
    return statuses


def load_case_editability_review(
    case_id: str,
    *,
    root: Path | None = None,
) -> EditabilityReview | None:
    path = benchmark_root(root) / case_id / EDITABILITY_REVIEW_FILE
    payload = _read_review_json(path)
    if payload is None:
        return None
    return EditabilityReview.model_validate(payload)


def save_case_editability_review(
    review: EditabilityReview,
    *,
    root: Path | None = None,
) -> Path:
    if review.source != HumanVisualReviewSource.MANUAL:
        msg = "Benchmark editability reviews saved from the UI must use source=manual"
        raise ValueError(msg)
    if not review.reviewer.strip():
        raise WorkflowError("请填写评审人姓名后再保存可编辑性评审。")
    case_directory = benchmark_root(root) / review.case_id
    if not case_directory.is_dir():
        msg = f"Unknown benchmark case directory: {review.case_id}"
        raise ValueError(msg)
    from tests.benchmark.architectural_slides.render_manifest import editability_review_eligibility

    eligible, blockers = editability_review_eligibility(case_directory)
    if not eligible:
        detail = "；".join(blockers) if blockers else "PPTX unavailable"
        raise WorkflowError(f"可编辑性评审须基于 RenderScene 导出的 output.pptx。（{detail}）")
    if review.passed and review.major_problems:
        raise WorkflowError("存在 major_problems 时不可标记可编辑性通过。")
    if review.passed and not review.passes_threshold():
        raise WorkflowError("可编辑性综合分未达阈值，不可标记为通过。")
    if review.reviewed_at is None:
        review = review.model_copy(update={"reviewed_at": datetime.now(UTC)})
    if review.review_completed is False and review.reviewed_at is not None:
        review = review.model_copy(update={"review_completed": True})
    path = case_directory / EDITABILITY_REVIEW_FILE
    path.write_text(
        json.dumps(review.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


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
    from tests.benchmark.architectural_slides.render_manifest import (
        final_render_path as case_final_render_path,
        pptx_render_path as case_pptx_render_path,
        scene_preview_path as case_scene_preview_path,
        wireframe_path as case_wireframe_path,
    )

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
                preview_path=case_wireframe_path(directory),
                wireframe_path=case_wireframe_path(directory),
                scene_preview_path=case_scene_preview_path(directory),
                pptx_render_path=case_pptx_render_path(directory),
                final_render_path=case_final_render_path(directory),
                human_review_path=_visual_review_path(directory),
                layout_review_path=directory / HUMAN_LAYOUT_REVIEW_FILE,
                editability_review_path=directory / EDITABILITY_REVIEW_FILE,
                layout_score=layout_score,
                rule_passed=rule_passed,
            )
        )
    return summaries


def _visual_review_path(case_dir: Path) -> Path:
    primary = case_dir / HUMAN_VISUAL_REVIEW_FILE
    if primary.is_file():
        return primary
    return case_dir / LEGACY_HUMAN_REVIEW_FILE


def _read_review_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def load_case_review(case_id: str, *, root: Path | None = None) -> HumanVisualReview | None:
    case_dir = benchmark_root(root) / case_id
    for name in (HUMAN_VISUAL_REVIEW_FILE, LEGACY_HUMAN_REVIEW_FILE):
        payload = _read_review_json(case_dir / name)
        if payload is not None:
            return HumanVisualReview.model_validate(payload)
    return None


def load_case_layout_review(case_id: str, *, root: Path | None = None) -> HumanLayoutReview | None:
    path = benchmark_root(root) / case_id / HUMAN_LAYOUT_REVIEW_FILE
    payload = _read_review_json(path)
    if payload is None:
        return None
    return HumanLayoutReview.model_validate(payload)


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
    case_directory = benchmark_root(root) / review.case_id
    if not case_directory.is_dir():
        msg = f"Unknown benchmark case directory: {review.case_id}"
        raise ValueError(msg)
    from tests.benchmark.architectural_slides.render_manifest import visual_review_eligibility

    eligible, _, blockers = visual_review_eligibility(case_directory)
    if not eligible:
        detail = "；".join(blockers) if blockers else "final render unavailable"
        raise WorkflowError(
            f"{BENCHMARK_VISUAL_REVIEW_REQUIRES_FINAL_RENDER}（{detail}）"
        )
    if review.accepted_for_delivery and review.major_problems:
        raise WorkflowError("存在 major_problems 时不可标记为可交付。")
    if review.accepted_for_delivery and not review.passes_threshold():
        raise WorkflowError("综合分未达交付阈值，不可标记为可交付。")
    if review.reviewed_at is None:
        review = review.model_copy(update={"reviewed_at": datetime.now(UTC)})
    review = review.model_copy(
        update={
            "review_completed": True,
            "accepted": review.accepted_for_delivery,
        }
    )
    path = case_directory / HUMAN_VISUAL_REVIEW_FILE
    path.write_text(
        json.dumps(review.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def save_case_layout_review(
    review: HumanLayoutReview,
    *,
    root: Path | None = None,
) -> Path:
    if review.source != HumanVisualReviewSource.MANUAL:
        msg = "Benchmark layout reviews saved from the UI must use source=manual"
        raise ValueError(msg)
    if not review.reviewer.strip():
        raise WorkflowError("请填写评审人姓名后再保存几何评审。")
    case_directory = benchmark_root(root) / review.case_id
    if not case_directory.is_dir():
        msg = f"Unknown benchmark case directory: {review.case_id}"
        raise ValueError(msg)
    wireframe = case_directory / "wireframe.png"
    legacy = case_directory / "preview.png"
    if not wireframe.is_file() and not legacy.is_file():
        raise WorkflowError("缺少 wireframe.png，无法保存 Layout Geometry 评审。")
    if review.accepted_for_geometry and review.major_problems:
        raise WorkflowError("存在 major_problems 时不可标记几何版式通过。")
    if review.accepted_for_geometry and not review.passes_threshold():
        raise WorkflowError("几何综合分未达阈值，不可标记为通过。")
    if review.reviewed_at is None:
        review = review.model_copy(update={"reviewed_at": datetime.now(UTC)})
    path = case_directory / HUMAN_LAYOUT_REVIEW_FILE
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
        if review.is_scaffold_review() or review.is_invalidated():
            placeholder += 1
            continue
        manual_total += 1
        if review.accepted_for_delivery:
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
    return write_benchmark_report(
        base / "reports",
        update=False,
        from_disk_only=True,
        root=base,
    )


def build_human_review_export(
    *,
    root: Path | None = None,
    include_pending_cases: bool = True,
) -> BenchmarkHumanReviewExport:
    """Collect manual reviews and optional pending-case queue for export."""
    cases = list_benchmark_cases(root=root)
    manual_reviews: list[HumanVisualReview] = []
    pending_cases: list[BenchmarkPendingCase] = []
    base = benchmark_root(root)

    for case in cases:
        review = load_case_review(case.case_id, root=root)
        if review is not None and review.is_manual_review():
            manual_reviews.append(review)
            continue
        if include_pending_cases:
            preview_rel = ""
            if case.preview_path.is_file():
                try:
                    preview_rel = str(case.preview_path.relative_to(base))
                except ValueError:
                    preview_rel = case.preview_path.name
            pending_cases.append(
                BenchmarkPendingCase(
                    case_id=case.case_id,
                    title=case.title,
                    category=case.category,
                    page_type=case.page_type,
                    preview_png=preview_rel,
                )
            )

    gate = evaluate_benchmark_human_gate(manual_reviews)
    return BenchmarkHumanReviewExport(
        exported_at=datetime.now(UTC),
        case_count=len(cases),
        manual_review_count=len(manual_reviews),
        pending_count=len(pending_cases),
        reviews=manual_reviews,
        pending_cases=pending_cases,
        human_quality_gate_passed=gate.passed,
        human_average_weighted_score=gate.average_weighted_score,
        human_quality_gate_reasons=gate.reasons,
    )


def export_human_review_bundle(
    output_path: Path,
    *,
    root: Path | None = None,
    include_pending_cases: bool = True,
) -> Path:
    """Write consolidated manual-review JSON for backup or offline handoff."""
    bundle = build_human_review_export(
        root=root,
        include_pending_cases=include_pending_cases,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(bundle.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return output_path


def default_human_review_export_path(*, root: Path | None = None) -> Path:
    return benchmark_root(root) / "reports" / "human_reviews_export.json"


def parse_human_review_import_payload(payload: object) -> list[HumanVisualReview]:
    """Accept export bundle or a plain list of review records."""
    if isinstance(payload, list):
        return [HumanVisualReview.model_validate(item) for item in payload]
    if not isinstance(payload, dict):
        msg = "Import payload must be a JSON object or array"
        raise ValueError(msg)
    if "reviews" in payload:
        bundle = BenchmarkHumanReviewExport.model_validate(payload)
        return list(bundle.reviews)
    msg = "Import payload missing 'reviews' array"
    raise ValueError(msg)


def import_human_review_bundle(
    source_path: Path,
    *,
    root: Path | None = None,
    skip_existing_manual: bool = False,
) -> HumanReviewImportResult:
    """Apply manual reviews from an export bundle onto per-case human_review.json files."""
    payload = json.loads(source_path.read_text(encoding="utf-8"))
    reviews = parse_human_review_import_payload(payload)
    known_ids = {case.case_id for case in list_benchmark_cases(root=root)}
    imported_paths: list[Path] = []
    skipped = 0
    rejected = 0

    for review in reviews:
        if not review.is_manual_review():
            rejected += 1
            continue
        if review.case_id not in known_ids:
            rejected += 1
            continue
        if not review.reviewer.strip():
            rejected += 1
            continue
        existing = load_case_review(review.case_id, root=root)
        if (
            skip_existing_manual
            and existing is not None
            and existing.is_manual_review()
        ):
            skipped += 1
            continue
        imported_paths.append(save_case_review(review, root=root))

    return HumanReviewImportResult(
        imported_count=len(imported_paths),
        skipped_count=skipped,
        rejected_count=rejected,
        paths=imported_paths,
    )


def _read_optional_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None
