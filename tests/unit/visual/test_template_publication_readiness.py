"""Unit tests for Phase 4 formal publication readiness and Phase 3.5 sign-off."""

from __future__ import annotations

from pathlib import Path

from archium.application.visual.architectural_content_schema_publish_gate import (
    ArchitecturalContentSchemaPublishGate,
)
from archium.application.visual.template_induction_service import TemplateInductionService
from archium.application.visual.template_publication_readiness import (
    TemplatePublicationReadinessService,
)
from archium.domain.visual.architectural_content_schema import SchemaTestFillResult
from archium.domain.visual.template_induction import Phase35HumanSignoff, TemplateInductionStatus
from tests.unit.reference_ppt_parser.conftest import write_architectural_reference_pptx
from tests.unit.visual.test_architectural_content_schema import (
    _gate_with_pass_fill,
    _PassThroughTestFill,
)


def test_formal_publish_requires_phase35_signoff(tmp_path: Path) -> None:
    pptx = write_architectural_reference_pptx(tmp_path / "ref.pptx", pages=16)
    service = TemplateInductionService()
    service.workspace_root = lambda induction_id: (tmp_path / "ind" / str(induction_id))  # type: ignore[method-assign]
    result = service.induce(pptx, capture_screenshots=False)
    schemas = list(result.schemas)
    for schema in schemas:
        schema.needs_review = False
        schema.human_corrected = True

    gate = ArchitecturalContentSchemaPublishGate(test_fill_service=_PassThroughTestFill())
    blocked = gate.evaluate(
        induction=result.induction,
        presentation=result.presentation,
        schemas=schemas,
        formal_publish=True,
    )
    assert blocked.status == "BLOCKED"
    assert any(b.code == "PHASE35_HUMAN_SIGNOFF_REQUIRED" for b in blocked.blockers)

    result.induction.phase35_signoff = Phase35HumanSignoff(
        status="PASS",
        reviewer="tester",
        run_reference="phase35_test",
    )
    cleared = gate.evaluate(
        induction=result.induction,
        presentation=result.presentation,
        schemas=schemas,
        formal_publish=True,
    )
    assert not any(b.code == "PHASE35_HUMAN_SIGNOFF_REQUIRED" for b in cleared.blockers)


def test_readiness_reports_five_gates(tmp_path: Path) -> None:
    pptx = write_architectural_reference_pptx(tmp_path / "ref.pptx", pages=16)
    service = TemplateInductionService()
    service.workspace_root = lambda induction_id: (tmp_path / "ind" / str(induction_id))  # type: ignore[method-assign]
    result = service.induce(pptx, capture_screenshots=False)
    schemas = list(result.schemas)

    report = _gate_with_pass_fill().evaluate(
        induction=result.induction,
        presentation=result.presentation,
        schemas=schemas,
        formal_publish=True,
    )
    readiness = TemplatePublicationReadinessService().evaluate(
        induction=result.induction,
        presentation=result.presentation,
        schemas=schemas,
        publish_report=report,
    )
    gate_ids = {g.gate_id for g in readiness.gates}
    assert gate_ids == {
        "phase35_human_signoff",
        "representative_classification",
        "cluster_level_schema",
        "schema_test_fill",
        "real_template_published",
    }
    assert readiness.overall in {"NEEDS_REVIEW", "BLOCKED", "PASS_WITH_WARNINGS"}


def test_record_signoff_persists_artifact(tmp_path: Path) -> None:
    pptx = write_architectural_reference_pptx(tmp_path / "ref.pptx", pages=16)
    service = TemplateInductionService()
    service.workspace_root = lambda induction_id: (tmp_path / "ind" / str(induction_id))  # type: ignore[method-assign]
    result = service.induce(pptx, capture_screenshots=False)

    service.record_phase35_signoff(
        result.induction,
        status="PASS_WITH_WARNINGS",
        reviewer="human",
        run_reference="phase35_run",
        workspace=result.workspace,
        presentation=result.presentation,
    )
    assert (result.workspace / "phase35_human_signoff.json").is_file()

    _, reloaded = service.load_workspace(result.workspace)
    assert reloaded.phase35_signoff is not None
    assert reloaded.phase35_signoff.status == "PASS_WITH_WARNINGS"
    assert reloaded.phase35_signoff.reviewer == "human"


def test_publish_with_signoff_and_pass_fill(tmp_path: Path) -> None:
    from archium.domain.visual.architectural_content_schema import SchemaPublishReport

    pptx = write_architectural_reference_pptx(tmp_path / "ref.pptx", pages=16)
    service = TemplateInductionService()
    service.workspace_root = lambda induction_id: (tmp_path / "ind" / str(induction_id))  # type: ignore[method-assign]
    service._publish_gate = _gate_with_pass_fill()  # type: ignore[assignment]
    result = service.induce(pptx, capture_screenshots=False)
    schemas = list(result.schemas)
    for schema in schemas:
        schema.needs_review = False
        schema.human_corrected = True

    result.induction.phase35_signoff = Phase35HumanSignoff(status="PASS", reviewer="tester")
    for classification in result.induction.classifications:
        if classification.slide_id in {
            c.representative_slide_id for c in result.induction.clusters
        }:
            classification.needs_review = False

    report = service.publish(result.induction, result.presentation, schemas=schemas)
    if report.status == "PASS":
        assert result.induction.status == TemplateInductionStatus.PUBLISHED
    else:
        assert report.status in {"PASS_WITH_WARNINGS", "BLOCKED"}

    # Warnings-only path still blocks published status.
    induction2 = result.induction.model_copy(deep=True)
    induction2.status = TemplateInductionStatus.REVIEW

    class _WarnGate:
        def evaluate(self, **_kwargs: object) -> SchemaPublishReport:
            return SchemaPublishReport(
                status="PASS_WITH_WARNINGS",
                warnings=["未识别封面页"],
                schema_ids=[s.id for s in schemas],
                test_fill_results=[
                    SchemaTestFillResult(
                        schema_id=s.id,
                        representative_slide_id=s.representative_slide_id,
                        render_valid=True,
                    )
                    for s in schemas
                ],
            )

    service._publish_gate = _WarnGate()  # type: ignore[assignment]
    service.publish(induction2, result.presentation, schemas=schemas)
    assert induction2.status != TemplateInductionStatus.PUBLISHED
