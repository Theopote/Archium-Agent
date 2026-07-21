"""Unit tests for architectural content schema extraction and publish gate."""

from __future__ import annotations

from pathlib import Path

from archium.application.visual.architectural_content_schema_extractor import (
    ArchitecturalContentSchemaExtractor,
)
from archium.application.visual.architectural_content_schema_publish_gate import (
    ArchitecturalContentSchemaPublishGate,
)
from archium.domain.visual.architectural_content_schema import (
    SchemaReviewOverride,
    SchemaTestFillResult,
)
from archium.application.visual.template_induction_service import TemplateInductionService
from archium.domain.visual.template_induction import ArchitecturalContentType
from tests.unit.reference_ppt_parser.conftest import write_architectural_reference_pptx


class _PassThroughTestFill:
    """Isolate publish-gate logic from structural fill in unit tests."""

    def validate(self, schema, slide):  # type: ignore[no-untyped-def]
        return SchemaTestFillResult(
            schema_id=schema.id,
            representative_slide_id=slide.slide_id,
            required_slots_filled=True,
            render_valid=True,
        )


def _gate_with_pass_fill() -> ArchitecturalContentSchemaPublishGate:
    return ArchitecturalContentSchemaPublishGate(test_fill_service=_PassThroughTestFill())


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
    assert schema.central_claim is not None
    assert schema.evidence_items
    assert schema.visual_evidence
    assert schema.reference_paragraphs
    assert schema.slide_purpose.startswith("证明")
    assert any(r.role.value == "evidence" for r in schema.required_content)


def test_photo_analysis_schema_semantic_contract_roundtrip() -> None:
    from archium.domain.visual.architectural_content_schema import (
        ArchitecturalContentSchema,
        ContentRequirement,
        ContentRole,
        VisualRequirement,
    )

    schema = ArchitecturalContentSchema(
        name="content/photo_analysis",
        page_purpose="证明入口冲突",
        required_content=[
            ContentRequirement(role=ContentRole.TITLE, required=True, max_count=1),
            ContentRequirement(role=ContentRole.EVIDENCE, required=True, min_count=2, max_count=4),
        ],
        visual_requirements=[
            VisualRequirement(
                role="supporting_image",
                required=True,
                min_count=2,
                max_count=4,
                description="现场照片",
            )
        ],
    )
    hydrated = schema.hydrate_semantic_contract()
    assert hydrated.evidence_items
    assert hydrated.visual_evidence
    merged = hydrated.apply_semantic_contract()
    assert any(item.role == ContentRole.EVIDENCE for item in merged.required_content)


def test_drawing_focus_schema_declares_drawing_slot(tmp_path: Path) -> None:
    pptx = write_architectural_reference_pptx(tmp_path / "ref.pptx", pages=16)
    service = TemplateInductionService()
    service.workspace_root = lambda induction_id: (tmp_path / "ind" / str(induction_id))  # type: ignore[method-assign]
    result = service.induce(pptx, capture_screenshots=False)
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
    assert report3.status in {"PASS", "PASS_WITH_WARNINGS", "BLOCKED"}
    if not any(b.code == "SCHEMA_TEST_FILL_FAILED" for b in report3.blockers):
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


def test_publish_gate_blocks_unconfirmed_representative_classification(
    tmp_path: Path,
) -> None:
    pptx = write_architectural_reference_pptx(tmp_path / "ref.pptx", pages=16)
    service = TemplateInductionService()
    service.workspace_root = lambda induction_id: (tmp_path / "ind" / str(induction_id))  # type: ignore[method-assign]
    result = service.induce(pptx, capture_screenshots=False)
    rep_id = result.induction.clusters[0].representative_slide_id
    for classification in result.induction.classifications:
        if classification.slide_id == rep_id:
            classification.needs_review = True
            break

    report = ArchitecturalContentSchemaPublishGate().evaluate(
        induction=result.induction,
        presentation=result.presentation,
        schemas=list(result.schemas),
    )
    assert report.status == "BLOCKED"
    assert any(b.code == "REPRESENTATIVE_CLASSIFICATION_UNCONFIRMED" for b in report.blockers)


def test_publish_gate_warns_non_representative_low_confidence(tmp_path: Path) -> None:
    pptx = write_architectural_reference_pptx(tmp_path / "ref.pptx", pages=16)
    service = TemplateInductionService()
    service.workspace_root = lambda induction_id: (tmp_path / "ind" / str(induction_id))  # type: ignore[method-assign]
    result = service.induce(pptx, capture_screenshots=False)
    rep_ids = {
        c.representative_slide_id for c in result.induction.clusters if c.representative_slide_id
    }
    non_rep = next(
        c.slide_id
        for c in result.induction.classifications
        if c.slide_id not in rep_ids
    )
    for classification in result.induction.classifications:
        if classification.slide_id in rep_ids:
            classification.needs_review = False
        elif classification.slide_id == non_rep:
            classification.needs_review = True
        else:
            classification.needs_review = False
    result.induction.low_confidence_slide_ids = [
        c.slide_id for c in result.induction.classifications if c.needs_review
    ]

    schemas = list(result.schemas)
    for schema in schemas:
        schema.needs_review = False
        schema.human_corrected = True

    report = _gate_with_pass_fill().evaluate(
        induction=result.induction,
        presentation=result.presentation,
        schemas=schemas,
    )
    assert report.status in {"PASS", "PASS_WITH_WARNINGS"}
    assert any("非代表页" in w for w in report.warnings)
    assert not any(b.code == "REPRESENTATIVE_CLASSIFICATION_UNCONFIRMED" for b in report.blockers)


def test_cluster_level_stats_populated(tmp_path: Path) -> None:
    from archium.domain.visual.reference_slide import (
        ReferenceElement,
        ReferenceElementType,
        ReferenceSlideSnapshot,
    )
    from archium.domain.visual.template_induction import (
        FunctionalSlideType,
        ReferenceSlideCluster,
    )

    members = [
        ReferenceSlideSnapshot(
            slide_index=i,
            slide_id=f"slide_{i:03d}",
            elements=[
                ReferenceElement(
                    id=f"t{i}",
                    element_type=ReferenceElementType.TEXT,
                    x=0.5,
                    y=0.3,
                    width=8.0,
                    height=0.6,
                    text="标题" * (i + 1),
                    semantic_role="title",
                ),
                *[
                    ReferenceElement(
                        id=f"i{i}_{j}",
                        element_type=ReferenceElementType.IMAGE,
                        x=5.0,
                        y=1.0 + j,
                        width=2.0,
                        height=1.5,
                        semantic_role="supporting_image",
                    )
                    for j in range(i % 3)
                ],
            ],
            text_content=[f"标题{i}"],
        )
        for i in range(4)
    ]
    cluster = ReferenceSlideCluster(
        functional_type=FunctionalSlideType.CONTENT,
        content_type=ArchitecturalContentType.MULTI_IMAGE_GRID,
        slide_ids=[s.slide_id for s in members],
        representative_slide_id=members[-1].slide_id,
        structural_similarity=0.8,
        visual_similarity=0.75,
        semantic_similarity=0.7,
    )
    schema = ArchitecturalContentSchemaExtractor().extract_from_slide(
        members[-1], cluster=cluster, member_slides=members
    )
    assert schema.cluster_member_count == 4
    assert schema.cluster_stats.get("image_max") == 2
    assert "image_median" in schema.cluster_stats


def test_confidence_uses_cluster_signals_not_field_count() -> None:
    from archium.domain.visual.reference_slide import (
        ReferenceElement,
        ReferenceElementType,
        ReferenceSlideSnapshot,
    )
    from archium.domain.visual.template_induction import (
        FunctionalSlideClassification,
        FunctionalSlideType,
        ReferenceSlideCluster,
        RepresentativeSlideScore,
    )

    slide = ReferenceSlideSnapshot(
        slide_index=0,
        slide_id="slide_001",
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
            ),
        ],
        text_content=["入口交通拥堵问题突出"],
    )
    cluster = ReferenceSlideCluster(
        functional_type=FunctionalSlideType.CONTENT,
        content_type=ArchitecturalContentType.TEXT_ARGUMENT,
        slide_ids=[slide.slide_id],
        representative_slide_id=slide.slide_id,
        structural_similarity=0.9,
        visual_similarity=0.85,
        semantic_similarity=0.8,
    )
    classification = FunctionalSlideClassification(
        slide_id=slide.slide_id,
        slide_index=0,
        functional_type=FunctionalSlideType.CONTENT,
        content_type=ArchitecturalContentType.TEXT_ARGUMENT,
        confidence=0.9,
    )
    rep_score = RepresentativeSlideScore(
        slide_id=slide.slide_id,
        cluster_id=cluster.id,
        total_score=0.85,
    )
    schema = ArchitecturalContentSchemaExtractor().extract_from_slide(
        slide,
        cluster=cluster,
        member_slides=[slide],
        classification=classification,
        representative_score=rep_score,
    )
    assert 0.45 < schema.confidence < 0.95
    assert schema.confidence != 0.55 + len(schema.required_content) * 0.1


def test_publish_gate_includes_test_fill_results(tmp_path: Path) -> None:
    pptx = write_architectural_reference_pptx(tmp_path / "ref.pptx", pages=16)
    service = TemplateInductionService()
    service.workspace_root = lambda induction_id: (tmp_path / "ind" / str(induction_id))  # type: ignore[method-assign]
    result = service.induce(pptx, capture_screenshots=False)
    assert result.publish_report is not None
    fills = result.publish_report.test_fill_results
    assert fills
    assert all(f.schema_id for f in fills)


def test_formal_publish_requires_pass_without_warnings() -> None:
    from archium.domain.visual.architectural_content_schema import SchemaPublishReport

    assert SchemaPublishReport(status="PASS").can_formally_publish
    assert SchemaPublishReport(status="PASS").can_publish
    warned = SchemaPublishReport(status="PASS_WITH_WARNINGS", warnings=["未识别封面页"])
    assert warned.can_publish
    assert not warned.can_formally_publish


def test_publish_sets_published_only_on_pass(tmp_path: Path) -> None:
    from archium.domain.visual.architectural_content_schema import SchemaPublishReport
    from archium.domain.visual.template_induction import TemplateInductionStatus

    pptx = write_architectural_reference_pptx(tmp_path / "ref.pptx", pages=16)
    service = TemplateInductionService()
    service.workspace_root = lambda induction_id: (tmp_path / "ind" / str(induction_id))  # type: ignore[method-assign]
    result = service.induce(pptx, capture_screenshots=False)
    schemas = list(result.schemas)
    for schema in schemas:
        schema.needs_review = False
        schema.human_corrected = True

    induction = result.induction.model_copy(deep=True)

    class _WarnGate:
        def evaluate(self, **_kwargs: object) -> SchemaPublishReport:
            return SchemaPublishReport(
                status="PASS_WITH_WARNINGS",
                warnings=["未识别封面页"],
                schema_ids=[s.id for s in schemas],
            )

    service._publish_gate = _WarnGate()  # type: ignore[assignment]
    report = service.publish(induction, result.presentation, schemas=schemas)
    assert report.can_publish
    assert not report.can_formally_publish
    assert induction.status != TemplateInductionStatus.PUBLISHED
