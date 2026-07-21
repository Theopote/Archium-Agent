"""Phase 4: evaluate formal template publication readiness for an induction workspace.

Usage:
    py scripts/run_phase4_template_publication.py --workspace output/.../induction/<id>
    py scripts/run_phase4_template_publication.py --workspace ... --attempt-publish
    py scripts/run_phase4_template_publication.py --workspace ... --record-signoff PASS --reviewer "Name"
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
    if not path.is_dir():
        raise FileNotFoundError(f"Workspace not found: {path}")
    if not (path / "induction_result.json").is_file():
        raise FileNotFoundError(f"Not an induction workspace (missing induction_result.json): {path}")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 4 template publication readiness")
    parser.add_argument(
        "--workspace",
        required=True,
        help="Induction workspace directory (contains induction_result.json)",
    )
    parser.add_argument(
        "--record-signoff",
        choices=["PASS", "PASS_WITH_WARNINGS", "NEEDS_REVIEW", "BLOCKED"],
        help="Record Phase 3.5 human sign-off before evaluating formal publish",
    )
    parser.add_argument("--reviewer", default="", help="Reviewer name for sign-off")
    parser.add_argument("--signoff-notes", default="", help="Optional sign-off notes")
    parser.add_argument(
        "--run-reference",
        default="",
        help="Phase 3.5 run id (e.g. phase35_20260721_074113)",
    )
    parser.add_argument(
        "--attempt-publish",
        action="store_true",
        help="Attempt formal publish when readiness allows",
    )
    parser.add_argument(
        "--materialize-template",
        action="store_true",
        help="After published induction, write architectural_template.json",
    )
    parser.add_argument(
        "--source-pptx",
        default="",
        help="Optional source PPTX to copy into template package",
    )
    args = parser.parse_args()

    workspace = _resolve_workspace(args.workspace)
    service = TemplateInductionService()
    presentation, induction = service.load_workspace(workspace)
    schemas = [
        ArchitecturalContentSchema.model_validate(item) for item in induction.content_schemas
    ]

    if args.record_signoff:
        if not args.reviewer.strip():
            print("ERROR: --reviewer required with --record-signoff", file=sys.stderr)
            return 2
        induction = service.record_phase35_signoff(
            induction,
            status=args.record_signoff,
            reviewer=args.reviewer,
            notes=args.signoff_notes,
            run_reference=args.run_reference,
            workspace=workspace,
            presentation=presentation,
        )
        print(f"Recorded Phase 3.5 sign-off: {args.record_signoff} by {args.reviewer}")

    report = ArchitecturalContentSchemaPublishGate().evaluate(
        induction=induction,
        presentation=presentation,
        schemas=schemas,
        formal_publish=True,
    )
    induction.publish_report = report.model_dump(mode="json")

    readiness = TemplatePublicationReadinessService().evaluate(
        induction=induction,
        presentation=presentation,
        schemas=schemas,
        publish_report=report,
    )

    out_path = workspace / "template_publication_readiness.json"
    payload = {
        "readiness": readiness.model_dump(mode="json"),
        "publish_report_status": report.status,
        "can_formally_publish": report.can_formally_publish,
        "induction_status": induction.status.value,
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Workspace: {workspace}")
    print(f"Publish gate: {report.status} (formal={report.can_formally_publish})")
    print(f"Readiness overall: {readiness.overall}")
    for gate in readiness.gates:
        print(f"  [{gate.status:20}] {gate.label}: {gate.detail}")
    print(f"Wrote {out_path}")

    if args.attempt_publish:
        if not readiness.can_formally_publish:
            print("BLOCKED: formal publish not allowed — fix gates above", file=sys.stderr)
            return 1
        published = service.publish(induction, presentation, schemas=schemas)
        service.export_artifacts(
            workspace, presentation, induction, schemas=schemas, publish_report=published
        )
        if not published.can_formally_publish:
            print(f"BLOCKED: publish returned {published.status}", file=sys.stderr)
            return 1
        print(f"SUCCESS: schema induction published — {induction.name}")

    if args.materialize_template:
        if induction.status.value != "published":
            print("BLOCKED: induction must be published before materialize", file=sys.stderr)
            return 1
        source = Path(args.source_pptx) if args.source_pptx else None
        mat = service.materialize_architectural_template(
            induction,
            presentation,
            workspace,
            schemas=schemas,
            source_pptx=source,
        )
        print(f"Materialized ArchitecturalTemplate {mat.template.id}")
        print(f"  layouts={len(mat.template.layouts)} schemas={len(mat.template.content_schemas)}")
        print(f"  artifact={mat.artifact_path}")
        return 0

    if args.attempt_publish and induction.status.value == "published":
        return 0

    return 0 if readiness.can_formally_publish else 1


if __name__ == "__main__":
    raise SystemExit(main())
