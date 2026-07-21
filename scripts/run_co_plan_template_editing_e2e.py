"""E2E: co-plan template_editing scene generation for an induction workspace.

Usage:
    py scripts/run_co_plan_template_editing_e2e.py --workspace output/.../induction/<id>
    py scripts/run_co_plan_template_editing_e2e.py --workspace ... --materialize-template
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from uuid import uuid4

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from archium.application.outline_templates import renovation_outline_sections  # noqa: E402
from archium.application.visual.induction_architectural_template_publisher import (  # noqa: E402
    InductionArchitecturalTemplatePublisher,
)
from archium.application.visual.outline_template_co_planning_service import (  # noqa: E402
    OutlineTemplateCoPlanningService,
)
from archium.application.visual.template_induction_service import (  # noqa: E402
    TemplateInductionService,
)
from archium.domain.outline import OutlinePlan  # noqa: E402
from archium.domain.visual.architectural_content_schema import (  # noqa: E402
    ArchitecturalContentSchema,
)
from archium.domain.visual.template_induction import TemplateInductionStatus  # noqa: E402


def _resolve_workspace(raw: str) -> Path:
    path = Path(raw).expanduser()
    if not path.is_dir():
        raise FileNotFoundError(f"Workspace not found: {path}")
    if not (path / "induction_result.json").is_file():
        raise FileNotFoundError(f"Not an induction workspace: {path}")
    return path


def _default_outline(presentation_id) -> OutlinePlan:  # type: ignore[no-untyped-def]
    sections = renovation_outline_sections()[:4]
    return OutlinePlan(
        presentation_id=presentation_id,
        title="改造汇报 E2E",
        thesis="以证据支持改造决策",
        audience="主管部门",
        purpose="汇报改造方案",
        sections=sections,
        target_slide_count=max(1, sum(s.estimated_slide_count for s in sections)),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Co-plan template_editing E2E runner")
    parser.add_argument(
        "--workspace",
        required=True,
        help="Induction workspace (induction_result.json)",
    )
    parser.add_argument(
        "--materialize-template",
        action="store_true",
        help="Write architectural_template.json when missing",
    )
    parser.add_argument(
        "--outline-json",
        default="",
        help="Optional outline_plan.json path (defaults to workspace/outline_plan.json or synthetic)",
    )
    args = parser.parse_args()

    workspace = _resolve_workspace(args.workspace)
    service = TemplateInductionService()
    presentation, induction = service.load_workspace(workspace)
    schemas = [
        ArchitecturalContentSchema.model_validate(item)
        for item in induction.content_schemas
    ]

    template = service.load_architectural_template(workspace)
    if template is None:
        if not args.materialize_template:
            print("ERROR: architectural_template.json missing; pass --materialize-template")
            return 2
        induction.status = TemplateInductionStatus.PUBLISHED
        InductionArchitecturalTemplatePublisher().publish_to_workspace(
            induction=induction,
            presentation=presentation,
            schemas=schemas,
            workspace=workspace,
        )
        template = service.load_architectural_template(workspace)
    assert template is not None

    outline_path = Path(args.outline_json) if args.outline_json else workspace / "outline_plan.json"
    outline = service.load_outline_plan(workspace) if outline_path.is_file() else None
    if outline is None:
        outline = _default_outline(uuid4())
        (workspace / "outline_plan.json").write_text(
            json.dumps(outline.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"Wrote synthetic outline_plan.json ({len(outline.sections)} sections)")

    co_plan = service.load_co_plan(workspace)
    if co_plan is None:
        co_plan = service.co_plan_outline(
            induction,
            outline,
            schemas=schemas,
            template=template,
            workspace=workspace,
        )
        print(f"Co-plan created: {co_plan.template_editing_page_ids}")

    batch, updated = service.execute_co_plan_template_editing(
        induction,
        outline,
        co_plan,
        presentation,
        template=template,
        workspace=workspace,
    )

    summary = {
        "workspace": str(workspace),
        "generated": batch.generated_count,
        "skipped": batch.skipped_count,
        "failed": batch.failed_count,
        "semantic_pages": sum(1 for p in batch.page_results if p.semantic_contract_active),
        "pages": [
            {
                "slide_id": p.slide_id,
                "status": p.status,
                "semantic_contract_active": p.semantic_contract_active,
                "expected_image_slots": p.expected_image_slots,
                "warnings": p.warnings[:5],
                "scene": p.edit_scene_relative_path,
            }
            for p in batch.page_results
        ],
    }
    report_path = workspace / "co_plan_template_editing_e2e_report.json"
    report_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Report: {report_path}")
    return 0 if batch.failed_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
