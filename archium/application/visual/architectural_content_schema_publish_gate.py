"""Publish gate for induced architectural content schemas."""

from __future__ import annotations

from typing import Literal

from archium.application.visual.architectural_content_schema_test_fill import (
    ArchitecturalContentSchemaTestFillService,
)
from archium.application.visual.schema_usage_validator import validate_schema_length_bounds
from archium.domain.visual.architectural_content_schema import (
    ArchitecturalContentSchema,
    SchemaPublishBlocker,
    SchemaPublishReport,
    SchemaTestFillResult,
)
from archium.domain.visual.reference_slide import ReferencePresentation
from archium.domain.visual.template_induction import (
    FunctionalSlideType,
    TemplateInductionResult,
)


class ArchitecturalContentSchemaPublishGate:
    """Enforce Phase 4 publish readiness without numeric scores."""

    def __init__(
        self,
        test_fill_service: ArchitecturalContentSchemaTestFillService | None = None,
    ) -> None:
        self._test_fill = test_fill_service or ArchitecturalContentSchemaTestFillService()

    def evaluate(
        self,
        *,
        induction: TemplateInductionResult,
        presentation: ReferencePresentation,
        schemas: list[ArchitecturalContentSchema],
        formal_publish: bool = False,
    ) -> SchemaPublishReport:
        blockers: list[SchemaPublishBlocker] = []
        warnings: list[str] = []
        test_fill_results: list[SchemaTestFillResult] = []
        schema_by_cluster = {s.cluster_id: s for s in schemas if s.cluster_id}
        representative_ids = {
            cluster.representative_slide_id
            for cluster in induction.clusters
            if cluster.representative_slide_id
        }

        if formal_publish:
            signoff = induction.phase35_signoff
            if signoff is None or not signoff.allows_formal_publish:
                blockers.append(
                    SchemaPublishBlocker(
                        code="PHASE35_HUMAN_SIGNOFF_REQUIRED",
                        message="未完成 Phase 3.5 真人结构复核签署（需 PASS 或 PASS_WITH_WARNINGS）",
                    )
                )

        # Functional pages identified.
        functional_types = {c.functional_type for c in induction.classifications}
        if FunctionalSlideType.COVER not in functional_types:
            warnings.append("未识别封面页")
        if FunctionalSlideType.CONTENT not in functional_types:
            blockers.append(
                SchemaPublishBlocker(
                    code="MISSING_CONTENT_PAGES",
                    message="未识别任何内容页，无法发布模板",
                )
            )

        by_id = {s.slide_id: s for s in presentation.slides}

        # Every cluster has representative + schema.
        for cluster in induction.clusters:
            if not cluster.representative_slide_id:
                blockers.append(
                    SchemaPublishBlocker(
                        code="MISSING_REPRESENTATIVE",
                        message="聚类缺少代表页面",
                        cluster_id=cluster.id,
                    )
                )
                continue

            rep_classification = induction.classification_for(cluster.representative_slide_id)
            if rep_classification is not None and rep_classification.needs_review:
                blockers.append(
                    SchemaPublishBlocker(
                        code="REPRESENTATIVE_CLASSIFICATION_UNCONFIRMED",
                        message="代表页功能分类待复核，阻塞 Schema 发布",
                        cluster_id=cluster.id,
                        slide_id=cluster.representative_slide_id,
                    )
                )

            schema = schema_by_cluster.get(cluster.id)
            if schema is None:
                blockers.append(
                    SchemaPublishBlocker(
                        code="MISSING_SCHEMA",
                        message="代表页面缺少内容 Schema",
                        cluster_id=cluster.id,
                        slide_id=cluster.representative_slide_id,
                    )
                )
                continue

            if not schema.page_purpose.strip():
                blockers.append(
                    SchemaPublishBlocker(
                        code="EMPTY_PAGE_PURPOSE",
                        message="Schema 缺少页面用途",
                        cluster_id=cluster.id,
                        slide_id=schema.representative_slide_id,
                        schema_id=schema.id,
                    )
                )

            for message in validate_schema_length_bounds(schema):
                blockers.append(
                    SchemaPublishBlocker(
                        code="LENGTH_BOUNDS_INVALID",
                        message=message,
                        cluster_id=cluster.id,
                        slide_id=schema.representative_slide_id,
                        schema_id=schema.id,
                    )
                )

            if not schema.required_content:
                blockers.append(
                    SchemaPublishBlocker(
                        code="MISSING_REQUIRED_SLOTS",
                        message="未识别必填内容槽位",
                        cluster_id=cluster.id,
                        slide_id=schema.representative_slide_id,
                        schema_id=schema.id,
                    )
                )

            # Image vs drawing slots must be distinguished when either is present.
            if schema.supports_drawing and not schema.has_drawing_slot():
                blockers.append(
                    SchemaPublishBlocker(
                        code="DRAWING_SLOT_UNDECLARED",
                        message="支持图纸但未声明 drawing 视觉槽位",
                        cluster_id=cluster.id,
                        slide_id=schema.representative_slide_id,
                        schema_id=schema.id,
                    )
                )
            if schema.has_image_slot() and schema.has_drawing_slot():
                pass
            elif schema.min_asset_count > 0 and not (
                schema.has_image_slot() or schema.has_drawing_slot()
            ):
                blockers.append(
                    SchemaPublishBlocker(
                        code="ASSET_SLOTS_UNDECLARED",
                        message="需要素材但未区分图片/图纸槽位",
                        cluster_id=cluster.id,
                        slide_id=schema.representative_slide_id,
                        schema_id=schema.id,
                    )
                )

            if "reference_template" not in schema.forbidden_asset_origins:
                blockers.append(
                    SchemaPublishBlocker(
                        code="REFERENCE_TEMPLATE_NOT_FORBIDDEN",
                        message="禁止素材来源必须包含 reference_template",
                        cluster_id=cluster.id,
                        slide_id=schema.representative_slide_id,
                        schema_id=schema.id,
                    )
                )

            if schema.needs_review and not schema.human_corrected:
                blockers.append(
                    SchemaPublishBlocker(
                        code="SCHEMA_NEEDS_REVIEW",
                        message="低置信度 Schema 尚未人工确认",
                        cluster_id=cluster.id,
                        slide_id=schema.representative_slide_id,
                        schema_id=schema.id,
                    )
                )

            slide = by_id.get(cluster.representative_slide_id)
            if slide is not None:
                if slide.parse_warnings:
                    blockers.append(
                        SchemaPublishBlocker(
                            code="UNPARSEABLE_ELEMENTS",
                            message="代表页存在无法解析元素："
                            + "; ".join(slide.parse_warnings[:3]),
                            cluster_id=cluster.id,
                            slide_id=slide.slide_id,
                            schema_id=schema.id,
                        )
                    )
                if not slide.elements:
                    warnings.append(f"{slide.slide_id} 无可用元素，填测可能失败")

                fill_result = self._test_fill.validate(schema, slide)
                test_fill_results.append(fill_result)
                schema.test_fill_passed = fill_result.render_valid
                if not fill_result.render_valid:
                    blockers.append(
                        SchemaPublishBlocker(
                            code="SCHEMA_TEST_FILL_FAILED",
                            message="; ".join(fill_result.blockers[:3])
                            or "测试内容填充未通过",
                            cluster_id=cluster.id,
                            slide_id=slide.slide_id,
                            schema_id=schema.id,
                        )
                    )

        # Non-representative low-confidence classifications — warning only.
        open_review = [
            sid
            for sid in induction.low_confidence_slide_ids
            if any(c.slide_id == sid and c.needs_review for c in induction.classifications)
        ]
        non_rep_review = [sid for sid in open_review if sid not in representative_ids]
        if non_rep_review:
            warnings.append(
                f"仍有 {len(non_rep_review)} 页非代表页功能分类待复核（不阻塞 Schema 发布）"
            )

        status: Literal["PASS", "PASS_WITH_WARNINGS", "NEEDS_REVIEW", "BLOCKED"]
        if blockers:
            status = "BLOCKED"
        elif warnings:
            status = "PASS_WITH_WARNINGS"
        else:
            status = "PASS"

        return SchemaPublishReport(
            status=status,
            blockers=blockers,
            warnings=warnings,
            schema_ids=[s.id for s in schemas],
            test_fill_results=test_fill_results,
        )
