"""Build HTML/JSON reports for architectural slide benchmarks."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from html import escape
from pathlib import Path
from typing import Any, cast

from archium.domain.visual.benchmark import HumanVisualReview

from tests.benchmark.architectural_slides.artifacts import BENCHMARK_ROOT, case_dir
from tests.benchmark.architectural_slides.case_registry import get_case_definition
from tests.benchmark.architectural_slides.human_review_summary import human_review_summary_fields
from tests.benchmark.architectural_slides.runner import run_all_cases


def build_benchmark_summary(*, update: bool = False) -> dict[str, Any]:
    summaries = run_all_cases(update=update)
    cases: list[dict[str, Any]] = []
    for summary in summaries:
        definition = get_case_definition(summary.case_id)
        directory = case_dir(summary.case_id)
        human_payload = _read_optional_json(directory / "human_review.json")
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
                "preview_png": str((directory / "preview.png").relative_to(BENCHMARK_ROOT)),
                "rule_passed": summary.passed,
                "layout_score": summary.layout_score,
                "has_critical": summary.has_critical,
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
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "case_count": len(cases),
        "rule_passed_count": passed_count,
        "rule_pass_rate": round(passed_count / len(cases), 3) if cases else 0.0,
        "manual_human_review_count": manual_review_count,
        "manual_human_accepted_count": manual_accepted_count,
        "placeholder_human_review_count": placeholder_review_count,
        "human_quality_gate_passed": manual_accepted_count == len(cases) and len(cases) > 0,
        "cases": cases,
    }


def write_benchmark_report(output_dir: Path, *, update: bool = False) -> tuple[Path, Path]:
    summary = build_benchmark_summary(update=update)
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
        f"<p>人工评审: {summary.get('manual_human_review_count', 0)}/{summary['case_count']} · "
        f"可交付: {summary.get('manual_human_accepted_count', 0)}/{summary['case_count']} · "
        f"占位: {summary.get('placeholder_human_review_count', 0)}</p>"
        f"<p>人工质量门禁: "
        f"{'通过' if summary.get('human_quality_gate_passed') else '未通过（需真实 manual 评审）'}</p>"
        "<table><thead><tr>"
        "<th>Case</th><th>标题</th><th>页面类型</th><th>LayoutFamily</th>"
        "<th>预览</th><th>规则</th><th>规则分</th><th>人工分</th><th>评审来源</th><th>可交付</th><th>主要问题</th>"
        "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table></body></html>"
    )


def _read_optional_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
