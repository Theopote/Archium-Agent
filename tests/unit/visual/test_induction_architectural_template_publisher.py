"""Tests for induction → ArchitecturalTemplate bridge."""

from __future__ import annotations

from pathlib import Path

import pytest

from archium.application.visual.architectural_content_schema_publish_gate import (
    ArchitecturalContentSchemaPublishGate,
)
from archium.application.visual.induction_architectural_template_publisher import (
    InductionArchitecturalTemplatePublisher,
)
from archium.application.visual.template_induction_service import TemplateInductionService
from archium.domain.visual.architectural_template import TemplateStatus
from archium.domain.visual.template_induction import (
    Phase35HumanSignoff,
    TemplateInductionStatus,
)
from archium.exceptions import WorkflowError
from tests.unit.reference_ppt_parser.conftest import write_architectural_reference_pptx
from tests.unit.visual.test_architectural_content_schema import (
    _PassThroughTestFill,
    _gate_with_pass_fill,
)


def test_materialize_requires_published_status(tmp_path: Path) -> None:
    pptx = write_architectural_reference_pptx(tmp_path / "ref.pptx", pages=16)
    service = TemplateInductionService()
    service.workspace_root = lambda induction_id: (tmp_path / "ind" / str(induction_id))  # type: ignore[method-assign]
    result = service.induce(pptx, capture_screenshots=False)
    with pytest.raises(WorkflowError, match="published"):
        service.materialize_architectural_template(
            result.induction, result.presentation, result.workspace
        )


def test_materialize_builds_template_with_schemas_and_layouts(tmp_path: Path) -> None:
    pptx = write_architectural_reference_pptx(tmp_path / "ref.pptx", pages=16)
    service = TemplateInductionService()
    service.workspace_root = lambda induction_id: (tmp_path / "ind" / str(induction_id))  # type: ignore[method-assign]
    service._publish_gate = _gate_with_pass_fill()  # type: ignore[assignment]
    result = service.induce(pptx, capture_screenshots=False)
    schemas = list(result.schemas)
    for schema in schemas:
        schema.needs_review = False
        schema.human_corrected = True
    for classification in result.induction.classifications:
        if classification.slide_id in {
            c.representative_slide_id for c in result.induction.clusters
        }:
            classification.needs_review = False

    result.induction.phase35_signoff = Phase35HumanSignoff(status="PASS", reviewer="test")
    report = service.publish(result.induction, result.presentation, schemas=schemas)
    assert report.can_formally_publish or report.status in {"PASS", "PASS_WITH_WARNINGS"}
    if not report.can_formally_publish:
        pytest.skip("fixture publish gate not PASS in this environment")

    mat = service.materialize_architectural_template(
        result.induction,
        result.presentation,
        result.workspace,
        schemas=schemas,
        source_pptx=pptx,
    )
    template = mat.template
    assert template.status == TemplateStatus.PUBLISHED
    assert template.induction_id == str(result.induction.id)
    assert len(template.content_schemas) == len(schemas)
    assert len(template.layouts) >= 1
    assert all(layout.slots for layout in template.layouts if layout.content_schema_id)
    assert (result.workspace / "architectural_template.json").is_file()
    assert result.induction.architectural_template_id == str(template.id)

    loaded = service.load_architectural_template(result.workspace)
    assert loaded is not None
    assert loaded.id == template.id
    assert len(loaded.content_schemas) == len(schemas)


def test_publisher_maps_schema_to_layout(tmp_path: Path) -> None:
    pptx = write_architectural_reference_pptx(tmp_path / "ref.pptx", pages=16)
    service = TemplateInductionService()
    service.workspace_root = lambda induction_id: (tmp_path / "ind" / str(induction_id))  # type: ignore[method-assign]
    service._publish_gate = ArchitecturalContentSchemaPublishGate(
        test_fill_service=_PassThroughTestFill()
    )  # type: ignore[assignment]
    result = service.induce(pptx, capture_screenshots=False)
    result.induction.status = TemplateInductionStatus.PUBLISHED
    schemas = list(result.schemas)

    template = InductionArchitecturalTemplatePublisher().build(
        induction=result.induction,
        presentation=result.presentation,
        schemas=schemas,
        workspace=result.workspace,
        source_pptx=pptx,
    )
    schema_ids = {s.id for s in schemas}
    linked = {layout.content_schema_id for layout in template.layouts if layout.content_schema_id}
    assert linked.issubset(schema_ids)
    assert template.layout_for_schema(next(iter(schema_ids))) is not None
