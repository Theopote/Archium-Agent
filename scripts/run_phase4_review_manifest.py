"""Generate a human review manifest for Phase 4 template publication.

Usage:
    py scripts/run_phase4_review_manifest.py --workspace output/.../induction/<id>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from archium.application.visual.architectural_content_schema_publish_gate import (  # noqa: E402
    ArchitecturalContentSchemaPublishGate,
)
from archium.application.visual.template_induction_service import (  # noqa: E402
    TemplateInductionService,
)
from archium.application.visual.template_publication_readiness import (  # noqa: E402
    TemplatePublicationReadinessService,
)
from archium.domain.visual.architectural_content_schema import (  # noqa: E402
    ArchitecturalContentSchema,
)


def _resolve_workspace(raw: str) -> Path:
    path = Path(raw).expanduser()
    if not path.is_dir() or not (path / "induction_result.json").is_file():
        raise FileNotFoundError(f"Invalid induction workspace: {raw}")
    return path


def _render_markdown(
    *,
    workspace: Path,
    induction,
    presentation,
    schemas: list[ArchitecturalContentSchema],
    report,
    readiness,
) -> str:
    rep_ids = {
        c.representative_slide_id for c in induction.clusters if c.representative_slide_id
    }
    unconfirmed_reps: list[dict[str, object]] = []
    for cluster in induction.clusters:
        rep = cluster.representative_slide_id
        if not rep:
            continue
        clf = induction.classification_for(rep)
        if clf is None or not clf.needs_review:
            continue
        score = next((s for s in induction.representative_scores if s.slide_id == rep), None)
        unconfirmed_reps.append(
            {
                "cluster_id": cluster.id[:8],
                "slide_id": rep,
                "content_type": cluster.content_type.value,
                "size": len(cluster.slide_ids),
                "confidence": clf.confidence,
                "anomaly": score.anomaly_penalty if score else 0,
                "complexity": score.excessive_complexity_penalty if score else 0,
            }
        )

    fill_by_schema = {
        f.schema_id: f for f in (report.test_fill_results if report else [])
    }
    schema_rows: list[dict[str, object]] = []
    for schema in schemas:
        fill = fill_by_schema.get(schema.id)
        blockers = [b for b in report.blockers if b.schema_id == schema.id] if report else []
        schema_rows.append(
            {
                "slide_id": schema.representative_slide_id,
                "content_type": schema.content_type.value,
                "needs_review": schema.needs_review,
                "fill_ok": fill.render_valid if fill else None,
                "fill_blockers": fill.blockers[:2] if fill else [],
                "gate_blockers": [f"{b.code}" for b in blockers[:3]],
            }
        )

    lines = [
        "# Phase 4 正式发布复核清单",
        "",
        f"**工作区：** `{workspace}`",
        f"**模板：** {induction.name} · {induction.slide_count} 页 · status=`{induction.status.value}`",
        f"**发布门：** `{report.status if report else 'UNKNOWN'}`",
        f"**Readiness：** `{readiness.overall}` · 可正式发布={'是' if readiness.can_formally_publish else '否'}",
        "",
        "## 五项门槛",
        "",
        "| Gate | 状态 | 说明 |",
        "|------|------|------|",
    ]
    for gate in readiness.gates:
        lines.append(f"| {gate.label} | `{gate.status}` | {gate.detail} |")

    lines.extend(
        [
            "",
            f"## 代表页待复核（{len(unconfirmed_reps)}）",
            "",
            "在 UI 中：确认功能/内容类型，或换选同聚类内更典型的代表页。",
            "",
            "| 聚类 | 代表页 | 内容类型 | 成员数 | 置信度 | 异常罚分 | 复杂度罚分 | 操作 |",
            "|------|--------|----------|--------|--------|----------|------------|------|",
        ]
    )
    for row in unconfirmed_reps:
        lines.append(
            f"| `{row['cluster_id']}` | `{row['slide_id']}` | {row['content_type']} | "
            f"{row['size']} | {row['confidence']:.2f} | {row['anomaly']:.2f} | "
            f"{row['complexity']:.2f} | ☐ 已确认 |"
        )

    low_conf_non_rep = [
        sid for sid in induction.low_confidence_slide_ids if sid not in rep_ids
    ]
    if low_conf_non_rep:
        lines.extend(
            [
                "",
                f"## 非代表页低置信（{len(low_conf_non_rep)}，Warning 不阻塞）",
                "",
                ", ".join(f"`{sid}`" for sid in low_conf_non_rep[:20]),
            ]
        )

    failed_fills = [r for r in schema_rows if r["fill_ok"] is False]
    if failed_fills:
        lines.extend(
            [
                "",
                f"## 测试填充未通过（{len(failed_fills)}）",
                "",
                "| 代表页 | 内容类型 | Schema需确认 | 填充问题 | 发布阻断 |",
                "|--------|----------|--------------|----------|----------|",
            ]
        )
        for row in failed_fills:
            fill_msg = "; ".join(row["fill_blockers"]) if row["fill_blockers"] else "—"
            gate_msg = ", ".join(row["gate_blockers"]) if row["gate_blockers"] else "—"
            lines.append(
                f"| `{row['slide_id']}` | {row['content_type']} | "
                f"{'是' if row['needs_review'] else '否'} | {fill_msg} | {gate_msg} |"
            )

    needs_schema_review = [r for r in schema_rows if r["needs_review"]]
    if needs_schema_review:
        lines.extend(
            [
                "",
                f"## Schema 待人工确认（{len(needs_schema_review)}）",
                "",
                "UI → 展开对应 Schema → 修正用途/图纸/引用/图注 → **保存修正**。",
                "",
            ]
        )
        for row in needs_schema_review:
            lines.append(f"- `{row['slide_id']}` · {row['content_type']}")

    lines.extend(
        [
            "",
            "## 建议操作顺序",
            "",
            "1. 打开 **模板归纳复核**，粘贴上述工作区路径",
            "2. 逐项处理代表页待复核表",
            "3. 保存 Schema 人工修正",
            "4. 记录 Phase 3.5 签署（建议 Run B：`PASS_WITH_WARNINGS`）",
            "5. 运行 `run_phase4_template_publication.py --attempt-publish`",
            "",
            "## Phase 3.5 签署",
            "",
            "☐ PASS  ☐ PASS_WITH_WARNINGS  ☐ NEEDS_REVIEW  ☐ BLOCKED",
            "",
            "Reviewer: __________  Date: __________",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 4 review manifest generator")
    parser.add_argument("--workspace", required=True)
    parser.add_argument(
        "--output",
        help="Markdown output path (default: <workspace>/phase4_review_manifest.md)",
    )
    args = parser.parse_args()

    workspace = _resolve_workspace(args.workspace)
    service = TemplateInductionService()
    presentation, induction = service.load_workspace(workspace)
    schemas = [
        ArchitecturalContentSchema.model_validate(item) for item in induction.content_schemas
    ]

    report = ArchitecturalContentSchemaPublishGate().evaluate(
        induction=induction,
        presentation=presentation,
        schemas=schemas,
        formal_publish=True,
    )
    readiness = TemplatePublicationReadinessService().evaluate(
        induction=induction,
        presentation=presentation,
        schemas=schemas,
        publish_report=report,
    )

    md = _render_markdown(
        workspace=workspace,
        induction=induction,
        presentation=presentation,
        schemas=schemas,
        report=report,
        readiness=readiness,
    )
    out = Path(args.output) if args.output else workspace / "phase4_review_manifest.md"
    out.write_text(md, encoding="utf-8")
    print(f"Wrote {out}")
    print(f"Representatives needing review: {sum(1 for c in induction.clusters if c.representative_slide_id and (clf := induction.classification_for(c.representative_slide_id)) and clf.needs_review)}")
    print(f"Test fill failures: {sum(1 for f in report.test_fill_results if not f.render_valid)}/{len(report.test_fill_results)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
