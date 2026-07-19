"""Read/write architectural slide benchmark artifacts."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from archium.application.visual.benchmark_service import BenchmarkCaseResult
from archium.domain.visual.benchmark import HumanVisualReview

from tests.benchmark.architectural_slides.fixtures import ensure_case_assets
from tests.golden.visual.composition.artifacts import (
    fingerprint_plan,
    fingerprint_report,
    maybe_export_pptx,
    render_layout_preview_png,
    score_baseline,
)

UPDATE_ENV = "UPDATE_ARCHITECTURAL_BENCHMARK_BASELINES"
BENCHMARK_ROOT = Path(__file__).resolve().parent


def case_dir(case_id: str) -> Path:
    return BENCHMARK_ROOT / case_id


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


def default_human_review(case_id: str) -> HumanVisualReview:
    """Template human review — scores default to pass threshold for CI scaffolding."""
    return HumanVisualReview(
        case_id=case_id,
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
        reviewer_notes="待人工视觉评审。",
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
    _write_json(directory / "deck_qa_report.json", fingerprint_deck_qa(result))
    _write_json(
        directory / "human_review.json",
        default_human_review(result.definition.case_id).model_dump(mode="json"),
    )
    (directory / "notes.md").write_text(default_notes(result), encoding="utf-8")
    render_layout_preview_png(result.plan, directory / "preview.png")
    maybe_export_pptx(
        result.plan,
        result.design_system,
        directory / "output.pptx",
        title=result.slide.title,
    )
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
        "human_review.json",
        "notes.md",
        "preview.png",
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
    return json.loads(path.read_text(encoding="utf-8"))
