"""Read/write architectural slide benchmark artifacts."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any, cast

from archium.application.visual.benchmark_service import BenchmarkCaseResult
from archium.domain.visual.benchmark import (
    EditabilityReview,
    HumanVisualReview,
    HumanVisualReviewSource,
)

from tests.benchmark.architectural_slides.fixtures import ensure_case_assets
from tests.golden.visual.composition.artifacts import (
    fingerprint_plan,
    fingerprint_report,
    render_layout_preview_png,
    score_baseline,
)

UPDATE_ENV = "UPDATE_ARCHITECTURAL_BENCHMARK_BASELINES"
STRICT_HUMAN_REVIEW_ENV = "STRICT_BENCHMARK_HUMAN_REVIEW"
BENCHMARK_ROOT = Path(__file__).resolve().parent
BENCHMARK_REPORTS_DIR = BENCHMARK_ROOT / "reports"


def case_dir(case_id: str) -> Path:
    return BENCHMARK_ROOT / case_id


def materialized_benchmark_case_ids(*, root: Path | None = None) -> tuple[str, ...]:
    """Case folders with committed on-disk baselines (excludes catalog-only edge cases)."""
    base = root or BENCHMARK_ROOT
    return tuple(
        sorted(
            path.name
            for path in base.glob("case_*")
            if path.is_dir() and (path / "input.json").is_file()
        )
    )


def fingerprint_slide_spec(result: BenchmarkCaseResult) -> dict[str, Any]:
    slide = result.slide
    return {
        "title": slide.title,
        "message": slide.message,
        "chapter_id": slide.chapter_id,
        "order": slide.order,
        "key_points": list(slide.key_points),
        "visual_requirements": [
            {
                "type": req.type.value,
                "description": req.description,
                "asset_count": len(req.preferred_asset_ids),
            }
            for req in slide.visual_requirements
        ],
        "source_count": len(slide.source_citations),
    }


def fingerprint_visual_intent(result: BenchmarkCaseResult) -> dict[str, Any]:
    intent = result.intent
    return {
        "communication_goal": intent.communication_goal,
        "dominant_content_type": intent.dominant_content_type.value,
        "density_level": intent.density_level.value,
        "continuity_role": intent.continuity_role.value,
        "preferred_layout_families": [item.value for item in intent.preferred_layout_families],
        "composition_strategy": intent.composition_strategy,
        "has_hero_asset": intent.hero_asset_id is not None,
        "supporting_asset_count": len(intent.supporting_asset_ids),
    }


def fingerprint_input(result: BenchmarkCaseResult, asset_paths: list[str]) -> dict[str, Any]:
    definition = result.definition
    return {
        "case_id": definition.case_id,
        "title": definition.title,
        "category": definition.category.value,
        "page_type": definition.page_type,
        "page_task": definition.page_task,
        "visual_focus": definition.visual_focus,
        "expected_layout_family": definition.expected_layout_family.value,
        "allowed_layout_variants": list(definition.allowed_layout_variants),
        "layout_variant": definition.layout_variant,
        "assets": asset_paths,
    }


def fingerprint_deck_qa(result: BenchmarkCaseResult) -> dict[str, Any]:
    score = result.rule_score
    return {
        "deck_qa_score": score.deck_qa_score,
        "passed": score.passed,
        "layout_valid": score.layout_valid,
        "layout_score": score.layout_score,
        "has_critical": score.has_critical,
        "blocking_issue_count": score.blocking_issue_count,
        "rule_codes": list(score.rule_codes),
    }


def default_editability_review(case_id: str) -> EditabilityReview:
    return EditabilityReview(
        case_id=case_id,
        source=HumanVisualReviewSource.PLACEHOLDER,
        text_editable=4,
        image_replaceable=4,
        layer_independence=4,
        chart_editable=4,
        font_usability=4,
        not_flattened=4,
        selection_ease=4,
        modification_ease=4,
        passed=False,
        reviewer_notes="占位模板；须基于 output.pptx 真实打开后填写 manual 评审。",
    )


def layout_score_payload(result: BenchmarkCaseResult) -> dict[str, Any]:
    baseline = score_baseline(result.report)
    return {
        "benchmark": "layout_geometry",
        "case_id": result.definition.case_id,
        "layout_score": baseline.get("score"),
        "layout_valid": baseline.get("valid"),
        "has_critical": baseline.get("has_critical"),
        "passed": result.rule_score.passed,
    }


def default_human_review(case_id: str) -> HumanVisualReview:
    review = HumanVisualReview(
        case_id=case_id,
        source=HumanVisualReviewSource.PLACEHOLDER,
        information_hierarchy=4,
        visual_focus=4,
        reading_order=4,
        image_text_relationship=4,
        whitespace_density=4,
        architectural_expression=4,
        aesthetic_finish=4,
        editability=4,
        major_problems=[],
        minor_problems=[],
        accepted=False,
        reviewer_notes="占位模板；分数不可用于验收，待真实人工评审替换。",
    )
    return review


def human_review_is_placeholder(review: HumanVisualReview) -> bool:
    """Return True when a benchmark review is not a real manual rating."""
    return review.is_scaffold_review()


def derive_benchmark_human_review(
    case_id: str,
    *,
    layout_score: float,
    layout_valid: bool,
) -> HumanVisualReview:
    """Derive a layout-QA stand-in review (not a manual human rating)."""
    base = 3.0 + min(2.0, max(0.0, layout_score) * 2.0)
    score = int(round(min(5.0, max(1.0, base))))
    return HumanVisualReview(
        case_id=case_id,
        source=HumanVisualReviewSource.LAYOUT_QA_DERIVED,
        information_hierarchy=score,
        visual_focus=score,
        reading_order=score,
        image_text_relationship=score,
        whitespace_density=score,
        architectural_expression=score,
        aesthetic_finish=max(1, score - 1),
        editability=score,
        major_problems=[] if layout_valid else ["layout validation failed"],
        minor_problems=[],
        accepted=layout_valid and base >= 3.5,
        reviewer_notes=(
            f"AUTO: layout QA rehearsal baseline (score {layout_score:.2f}); "
            "replace with manual human review."
        ),
    )


def default_notes(result: BenchmarkCaseResult) -> str:
    definition = result.definition
    return (
        f"# {definition.title}\n\n"
        f"- **页面类型**: {definition.page_type}\n"
        f"- **分类**: {definition.category.value}\n"
        f"- **预期版式**: `{definition.expected_layout_family.value}` / "
        f"`{definition.layout_variant}`\n"
        f"- **视觉重点**: {definition.visual_focus}\n\n"
        "## 修复记录\n\n"
        "- （暂无）\n"
    )


def write_case_artifacts(result: BenchmarkCaseResult) -> Path:
    """Write all benchmark artifacts for one case."""
    directory = case_dir(result.definition.case_id)
    directory.mkdir(parents=True, exist_ok=True)
    asset_paths = ensure_case_assets(result.definition.case_id, directory / "assets")

    _write_json(directory / "input.json", fingerprint_input(result, asset_paths))
    _write_json(directory / "slide_spec.json", fingerprint_slide_spec(result))
    _write_json(directory / "visual_intent.json", fingerprint_visual_intent(result))
    _write_json(directory / "layout_plan.json", fingerprint_plan(result.plan))
    _write_json(directory / "validation_report.json", fingerprint_report(result.report))
    _write_json(directory / "score_baseline.json", score_baseline(result.report))
    _write_json(directory / "layout_score.json", layout_score_payload(result))
    _write_json(directory / "deck_qa_report.json", fingerprint_deck_qa(result))
    derived_review = derive_benchmark_human_review(
        result.definition.case_id,
        layout_score=result.rule_score.layout_score,
        layout_valid=result.rule_score.layout_valid,
    )
    _write_json(
        directory / "layout_qa_review.json",
        derived_review.model_dump(mode="json"),
    )
    review_path = directory / "human_review.json"
    if not review_path.exists():
        _write_json(
            review_path,
            default_human_review(result.definition.case_id).model_dump(mode="json"),
        )
    editability_path = directory / "editability_review.json"
    if not editability_path.exists():
        _write_json(
            editability_path,
            default_editability_review(result.definition.case_id).model_dump(mode="json"),
        )
    (directory / "notes.md").write_text(default_notes(result), encoding="utf-8")
    wireframe = directory / "wireframe.png"
    render_layout_preview_png(result.plan, wireframe)
    legacy_preview = directory / "preview.png"
    if legacy_preview != wireframe:
        shutil.copy(wireframe, legacy_preview)
    asset_count = len(asset_paths)
    from tests.benchmark.architectural_slides.render_pipeline import (
        render_benchmark_visual_artifacts,
    )

    render_benchmark_visual_artifacts(result, directory)
    return directory


def assert_or_update_case_baseline(result: BenchmarkCaseResult) -> None:
    """Compare or regenerate committed benchmark artifacts."""
    if os.environ.get(UPDATE_ENV) == "1":
        write_case_artifacts(result)
        return

    directory = case_dir(result.definition.case_id)
    required = (
        "input.json",
        "slide_spec.json",
        "visual_intent.json",
        "layout_plan.json",
        "validation_report.json",
        "score_baseline.json",
        "deck_qa_report.json",
        "layout_qa_review.json",
        "human_review.json",
        "notes.md",
        "wireframe.png",
        "preview.png",
        "render_manifest.json",
    )
    for name in required:
        path = directory / name
        assert path.exists(), f"Missing benchmark baseline: {path}"

    assert _read_json(directory / "layout_plan.json") == fingerprint_plan(result.plan), (
        f"LayoutPlan drift in {result.definition.case_id}. "
        f"Re-run with {UPDATE_ENV}=1 after intentional changes."
    )
    assert _read_json(directory / "validation_report.json") == fingerprint_report(
        result.report
    ), (
        f"Validation drift in {result.definition.case_id}. "
        f"Re-run with {UPDATE_ENV}=1 after intentional changes."
    )
    assert _read_json(directory / "score_baseline.json") == score_baseline(result.report), (
        f"Score drift in {result.definition.case_id}. "
        f"Re-run with {UPDATE_ENV}=1 after intentional changes."
    )
    assert _read_json(directory / "input.json") == fingerprint_input(
        result,
        ensure_case_assets(result.definition.case_id, directory / "assets"),
    )
    assert _read_json(directory / "slide_spec.json") == fingerprint_slide_spec(result)
    assert _read_json(directory / "visual_intent.json") == fingerprint_visual_intent(result)
    assert _read_json(directory / "deck_qa_report.json") == fingerprint_deck_qa(result)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
