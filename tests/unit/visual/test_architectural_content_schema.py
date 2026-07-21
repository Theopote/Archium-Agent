"""Unit tests for architectural content schema extraction and publish gate."""

from __future__ import annotations

from pathlib import Path

from archium.application.visual.architectural_content_schema_extractor import (
    ArchitecturalContentSchemaExtractor,
)
from archium.application.visual.architectural_content_schema_publish_gate import (
    ArchitecturalContentSchemaPublishGate,
)
from archium.application.visual.template_induction_service import TemplateInductionService
from archium.domain.visual.architectural_content_schema import SchemaReviewOverride
from archium.domain.visual.template_induction import ArchitecturalContentType
from tests.unit.reference_ppt_parser.conftest import write_architectural_reference_pptx


def test_schema_extracted_for_each_cluster(tmp_path: Path) -> None:
    pptx = write_architectural_reference_pptx(tmp_path / "ref.pptx", pages=16)
    service = TemplateInductionService()
    service.workspace_root = lambda induction_id: (tmp_path / "ind" / str(induction_id))  # type: ignore[method-assign]
    result = service.induce(pptx, capture_screenshots=False)

    assert result.schemas
    assert len(result.schemas) == len(result.induction.clusters)
    assert (result.workspace / "content_schemas.json").is_file()
    assert (result.workspace / "schema_publish_report.json").is_file()

    for schema in result.schemas:
        assert schema.page_purpose
        assert schema.required_content
        assert "reference_template" in schema.forbidden_asset_origins
        assert schema.representative_slide_id


def test_photo_analysis_schema_forbids_reference_case() -> None:
    from archium.domain.visual.reference_slide import (
        ReferenceElement,
        ReferenceElementType,
        ReferenceSlideSnapshot,
    )
    from archium.domain.visual.template_induction import (
        ArchitecturalContentType,
        FunctionalSlideType,
        ReferenceSlideCluster,
    )

    slide = ReferenceSlideSnapshot(
        slide_index=3,
        slide_id="slide_004",
        elements=[
            ReferenceElement(
                id="t1",
                element_type=ReferenceElementType.TEXT,
                x=0.5,
                y=0.3,
                width=8.0,
                height=0.6,
                text="入口交通拥堵问题突出",
                semantic_role="title",
                font_size_pt=24,
            ),
            ReferenceElement(
                id="i1",
                element_type=ReferenceElementType.IMAGE,
                x=5.0,
                y=1.2,
                width=4.0,
                height=2.5,
                semantic_role="supporting_image",
            ),
            ReferenceElement(
                id="i2",
                element_type=ReferenceElementType.IMAGE,
                x=5.0,
                y=3.8,
                width=4.0,
                height=1.5,
                semantic_role="supporting_image",
            ),
        ],
        text_content=["入口交通拥堵问题突出", "现场判断：车行与人行冲突"],
    )
    cluster = ReferenceSlideCluster(
        functional_type=FunctionalSlideType.CONTENT,
        content_type=ArchitecturalContentType.PHOTO_ANALYSIS,
        slide_ids=[slide.slide_id],
        representative_slide_id=slide.slide_id,
    )
    schema = ArchitecturalContentSchemaExtractor().extract_from_slide(slide, cluster=cluster)
    assert schema.content_type == ArchitecturalContentType.PHOTO_ANALYSIS
    assert "project_upload" in schema.allowed_asset_origins
    assert "reference_case" in schema.forbidden_asset_origins
    assert schema.has_image_slot()
    assert any(r.role.value == "evidence" for r in schema.required_content)


def test_drawing_focus_schema_declares_drawing_slot(tmp_path: Path) -> None:
    pptx = write_architectural_reference_pptx(tmp_path / "ref.pptx", pages=16)
    service = TemplateInductionService()
    service.workspace_root = lambda induction_id: (tmp_path / "ind" / str(induction_id))  # type: ignore[method-assign]
    result = service.induce(pptx, capture_screenshots=False)
    drawing_schemas = [
        s
        for s in result.schemas
        if s.content_type == ArchitecturalContentType.DRAWING_FOCUS or s.supports_drawing
    ]
    # Fixture uses text cues for 总平面 — extractor should still mark drawing support
    # via content type even without real PNG drawings.
    assert any(
        s.content_type == ArchitecturalContentType.DRAWING_FOCUS for s in result.schemas
    )
    for schema in result.schemas:
        if schema.content_type == ArchitecturalContentType.DRAWING_FOCUS:
            assert schema.supports_drawing
            assert schema.has_drawing_slot()
            assert any(v.fit_mode == "contain" for v in schema.visual_requirements)


def test_publish_gate_blocks_until_review_schemas_corrected(tmp_path: Path) -> None:
    pptx = write_architectural_reference_pptx(tmp_path / "ref.pptx", pages=16)
    service = TemplateInductionService()
    service.workspace_root = lambda induction_id: (tmp_path / "ind" / str(induction_id))  # type: ignore[method-assign]
    result = service.induce(pptx, capture_screenshots=False)
    assert result.publish_report is not None

    # Force a schema into needs_review without human correction.
    schemas = list(result.schemas)
    schemas[0].needs_review = True
    schemas[0].human_corrected = False
    report = ArchitecturalContentSchemaPublishGate().evaluate(
        induction=result.induction,
        presentation=result.presentation,
        schemas=schemas,
    )
    assert report.status == "BLOCKED"
    assert any(b.code == "SCHEMA_NEEDS_REVIEW" for b in report.blockers)

    overrides = [
        SchemaReviewOverride(
            schema_id=schemas[0].id,
            page_purpose=schemas[0].page_purpose + "（已人工确认）",
            notes="confirmed",
        )
    ]
    # Clear needs_review on others for a clean publish attempt after correction.
    for schema in schemas[1:]:
        schema.needs_review = False
        schema.human_corrected = True
    induction, updated, report2 = service.apply_schema_overrides(
        result.induction, result.presentation, overrides
    )
    # Re-evaluate with fully corrected set.
    for schema in updated:
        schema.needs_review = False
        schema.human_corrected = True
    report3 = service.publish(induction, result.presentation, schemas=updated)
    assert report3.can_publish or report3.status == "PASS_WITH_WARNINGS"


def test_extractor_standalone_matches_cluster_count(tmp_path: Path) -> None:
    pptx = write_architectural_reference_pptx(tmp_path / "ref.pptx", pages=16)
    service = TemplateInductionService()
    service.workspace_root = lambda induction_id: (tmp_path / "ind" / str(induction_id))  # type: ignore[method-assign]
    result = service.induce(pptx, capture_screenshots=False)
    again = ArchitecturalContentSchemaExtractor().extract_for_induction(
        result.presentation, result.induction
    )
    assert len(again) == len(result.schemas)
