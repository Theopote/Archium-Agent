"""Build HTML/JSON reports for architectural slide benchmarks."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from html import escape
from pathlib import Path
from typing import Any, cast

from archium.application.human_review_gate import evaluate_benchmark_human_gate
from archium.domain.visual.benchmark import HumanVisualReview

from tests.benchmark.architectural_slides.artifacts import (
    BENCHMARK_ROOT,
    case_dir,
    materialized_benchmark_case_ids,
)
from tests.benchmark.architectural_slides.case_registry import get_case_definition
from tests.benchmark.architectural_slides.human_review_summary import human_review_summary_fields
from tests.benchmark.architectural_slides.render_manifest import (
    load_render_manifest,
    scene_preview_path,
    wireframe_path,
)
from tests.benchmark.architectural_slides.review_paths import read_visual_review_payload
from tests.benchmark.architectural_slides.runner import run_all_cases


def _preview_relative_path(directory: Path, base: Path) -> str:
    scene = scene_preview_path(directory)
    if scene.is_file():
        return str(scene.relative_to(base))
    wire = wireframe_path(directory)
    if wire.is_file():
        return str(wire.relative_to(base))
    legacy = directory / "preview.png"
    return str(legacy.relative_to(base)) if legacy.is_file() else ""


def _render_fields_from_manifest(directory: Path) -> dict[str, Any]:
    manifest = load_render_manifest(directory)
    if manifest is None:
        return {"render_valid": False, "render_source": "pending", "scene_hash": ""}
    return {
        "render_valid": manifest.render_valid,
        "render_source": manifest.render_source,
        "scene_hash": manifest.scene_hash,
    }


def build_benchmark_summary(
    *,
    update: bool = False,
    from_disk_only: bool = False,
    root: Path | None = None,
) -> dict[str, Any]:
    if from_disk_only:
        return _build_benchmark_summary_from_disk(root=root)
    summaries = run_all_cases(update=update)
    cases: list[dict[str, Any]] = []
    for summary in summaries:
        definition = get_case_definition(summary.case_id)
        directory = case_dir(summary.case_id)
        human_payload = read_visual_review_payload(directory)
        human = HumanVisualReview.model_validate(human_payload) if human_payload else None
        human_fields = human_review_summary_fields(human)
        cases.append(
            {
                "case_id": summary.case_id,
                "title": definition.title,
                "category": definition.category.value,
                "page_type": definition.page_type,
                "layout_family": definition.expected_layout_family.value,
                "layout_variant": definition.layout_variant,
                "preview_png": _preview_relative_path(directory, BENCHMARK_ROOT),
                "rule_passed": summary.passed,
                "layout_score": summary.layout_score,
                "has_critical": summary.has_critical,
                **_render_fields_from_manifest(directory),
                **human_fields,
            }
        )
    passed_count = sum(1 for item in cases if item["rule_passed"])
    manual_accepted_count = sum(
        1 for item in cases if item["human_accepted_for_delivery"]
    )
    manual_review_count = sum(
        1
        for item in cases
        if item.get("human_review_source") == "manual"
    )
    placeholder_review_count = sum(
        1
        for item in cases
        if item.get("human_review_source") in {"placeholder", "layout_qa_derived"}
    )
    manual_reviews: list[HumanVisualReview] = []
    for summary in summaries:
        directory = case_dir(summary.case_id)
        human_payload = read_visual_review_payload(directory)
        if human_payload is None:
            continue
        review = HumanVisualReview.model_validate(human_payload)
        if review.is_manual_review():
            manual_reviews.append(review)
    human_gate = evaluate_benchmark_human_gate(manual_reviews)
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "case_count": len(cases),
        "rule_passed_count": passed_count,
        "rule_pass_rate": round(passed_count / len(cases), 3) if cases else 0.0,
        "manual_human_review_count": manual_review_count,
        "manual_human_accepted_count": manual_accepted_count,
        "placeholder_human_review_count": placeholder_review_count,
        "human_average_weighted_score": human_gate.average_weighted_score,
        "human_quality_gate_passed": human_gate.passed,
        "human_quality_gate_reasons": human_gate.reasons,
        "page_quality_status_counts": human_gate.page_quality_status_counts or {},
        "formal_gate_mode": "problem_driven",
        "cases": cases,
    }


def _build_benchmark_summary_from_disk(*, root: Path | None = None) -> dict[str, Any]:
    """Refresh summary from committed case folders without re-running layout builds."""
    base = root or BENCHMARK_ROOT
    cases: list[dict[str, Any]] = []
    manual_reviews: list[HumanVisualReview] = []
    for case_id in materialized_benchmark_case_ids(root=base):
        definition = get_case_definition(case_id)
        directory = case_dir(case_id) if root is None else base / case_id
        rule_fields = _rule_fields_from_baseline(directory)
        human_payload = read_visual_review_payload(directory)
        human = HumanVisualReview.model_validate(human_payload) if human_payload else None
        human_fields = human_review_summary_fields(human)
        if human is not None and human.is_manual_review():
            manual_reviews.append(human)
        preview_png = _preview_relative_path(directory, base)
        cases.append(
            {
                "case_id": case_id,
                "title": definition.title,
                "category": definition.category.value,
                "page_type": definition.page_type,
                "layout_family": definition.expected_layout_family.value,
                "layout_variant": definition.layout_variant,
                "preview_png": preview_png,
                **_render_fields_from_manifest(directory),
                **rule_fields,
                **human_fields,
            }
        )
    human_gate = evaluate_benchmark_human_gate(manual_reviews)
    passed_count = sum(1 for item in cases if item["rule_passed"])
    manual_accepted_count = sum(
        1 for item in cases if item["human_accepted_for_delivery"]
    )
    manual_review_count = sum(
        1 for item in cases if item.get("human_review_source") == "manual"
    )
    placeholder_review_count = sum(
        1
        for item in cases
        if item.get("human_review_source") in {"placeholder", "layout_qa_derived"}
    )
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "case_count": len(cases),
        "rule_passed_count": passed_count,
        "rule_pass_rate": round(passed_count / len(cases), 3) if cases else 0.0,
        "manual_human_review_count": manual_review_count,
        "manual_human_accepted_count": manual_accepted_count,
        "placeholder_human_review_count": placeholder_review_count,
        "human_average_weighted_score": human_gate.average_weighted_score,
        "human_quality_gate_passed": human_gate.passed,
        "human_quality_gate_reasons": human_gate.reasons,
        "page_quality_status_counts": human_gate.page_quality_status_counts or {},
        "formal_gate_mode": "problem_driven",
        "cases": cases,
    }


def _rule_fields_from_baseline(directory: Path) -> dict[str, Any]:
    score_payload = _read_optional_json(directory / "score_baseline.json")
    if score_payload is None:
        return {
            "rule_passed": False,
            "layout_score": None,
            "has_critical": None,
        }
    raw_score = score_payload.get("score")
    layout_score = float(raw_score) if isinstance(raw_score, (int, float)) else None
    valid = score_payload.get("valid")
    has_critical = score_payload.get("has_critical")
    rule_passed = False
    if isinstance(valid, bool) and isinstance(has_critical, bool):
        rule_passed = valid and not has_critical
    return {
        "rule_passed": rule_passed,
        "layout_score": layout_score,
        "has_critical": has_critical if isinstance(has_critical, bool) else None,
    }


def write_benchmark_report(
    output_dir: Path,
    *,
    update: bool = False,
    from_disk_only: bool | None = None,
    root: Path | None = None,
) -> tuple[Path, Path]:
    disk_only = not update if from_disk_only is None else from_disk_only
    summary = build_benchmark_summary(
        update=update,
        from_disk_only=disk_only,
        root=root or output_dir.parent,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "benchmark-summary.json"
    html_path = output_dir / "benchmark-report.html"
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    html_path.write_text(_render_html(summary), encoding="utf-8")
    return html_path, json_path


def _render_html(summary: dict[str, Any]) -> str:
    rows: list[str] = []
    for item in summary["cases"]:
        preview = escape(str(item["preview_png"]))
        rows.append(
            "<tr>"
            f"<td>{escape(item['case_id'])}</td>"
            f"<td>{escape(item['title'])}</td>"
            f"<td>{escape(item['page_type'])}</td>"
            f"<td><code>{escape(item['layout_family'])}</code></td>"
            f"<td><img src=\"{preview}\" alt=\"preview\" width=\"180\" /></td>"
            f"<td>{'通过' if item['rule_passed'] else '未通过'}</td>"
            f"<td>{item['layout_score']}</td>"
            f"<td>{'有效' if item.get('render_valid') else '无效'}</td>"
            f"<td>{escape(str(item.get('human_score_label') or '—'))}</td>"
            f"<td>{escape(str(item.get('human_review_source') or '—'))}</td>"
            f"<td>{'是' if item.get('human_accepted_for_delivery') else '否'}</td>"
            f"<td>{', '.join(escape(p) for p in item['major_problems']) or '—'}</td>"
            "</tr>"
        )
    return (
        "<!DOCTYPE html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\" />"
        "<title>Architectural Slide Benchmark Report</title>"
        "<style>body{font-family:sans-serif;margin:24px}table{border-collapse:collapse;width:100%}"
        "th,td{border:1px solid #ddd;padding:8px;vertical-align:top}th{background:#f5f5f5}</style>"
        "</head><body>"
        "<h1>Architectural Slide Benchmark</h1>"
        f"<p>生成时间: {escape(str(summary['generated_at']))}</p>"
        f"<p>规则通过: {summary['rule_passed_count']}/{summary['case_count']} "
        f"({summary['rule_pass_rate']:.1%})</p>"
        f"<p>人工异常复核: {summary.get('manual_human_review_count', 0)}/{summary['case_count']} · "
        f"可交付: {summary.get('manual_human_accepted_count', 0)}/{summary['case_count']} · "
        f"占位: {summary.get('placeholder_human_review_count', 0)} · "
        f"模式: {escape(str(summary.get('formal_gate_mode', 'problem_driven')))}</p>"
        f"<p>人工质量门禁（问题驱动）: "
        f"{'通过' if summary.get('human_quality_gate_passed') else '未通过（需异常复核）'}</p>"
        "<table><thead><tr>"
        "<th>Case</th><th>标题</th><th>页面类型</th><th>LayoutFamily</th>"
        "<th>预览</th><th>规则</th><th>规则分</th><th>渲染</th><th>状态</th><th>评审来源</th><th>可交付</th><th>主要问题</th>"
        "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table></body></html>"
    )


def _read_optional_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
