"""Publish gate for induced architectural content schemas."""

from __future__ import annotations

from archium.domain.visual.architectural_content_schema import (
    ArchitecturalContentSchema,
    SchemaPublishBlocker,
    SchemaPublishReport,
)
from archium.domain.visual.reference_slide import ReferencePresentation
from archium.domain.visual.template_induction import (
    FunctionalSlideType,
    TemplateInductionResult,
)


class ArchitecturalContentSchemaPublishGate:
    """Enforce Phase 4 publish readiness without numeric scores."""

    def evaluate(
        self,
        *,
        induction: TemplateInductionResult,
        presentation: ReferencePresentation,
        schemas: list[ArchitecturalContentSchema],
    ) -> SchemaPublishReport:
        blockers: list[SchemaPublishBlocker] = []
        warnings: list[str] = []
        schema_by_cluster = {s.cluster_id: s for s in schemas if s.cluster_id}

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
                    )
                )

            if not schema.required_content:
                blockers.append(
                    SchemaPublishBlocker(
                        code="MISSING_REQUIRED_SLOTS",
                        message="未识别必填内容槽位",
                        cluster_id=cluster.id,
                        slide_id=schema.representative_slide_id,
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
                    )
                )
            if schema.has_image_slot() and schema.has_drawing_slot():
                # OK — explicitly distinguished.
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
                    )
                )

            if "reference_template" not in schema.forbidden_asset_origins:
                blockers.append(
                    SchemaPublishBlocker(
                        code="REFERENCE_TEMPLATE_NOT_FORBIDDEN",
                        message="禁止素材来源必须包含 reference_template",
                        cluster_id=cluster.id,
                        slide_id=schema.representative_slide_id,
                    )
                )

            if schema.needs_review and not schema.human_corrected:
                blockers.append(
                    SchemaPublishBlocker(
                        code="SCHEMA_NEEDS_REVIEW",
                        message="低置信度 Schema 尚未人工确认",
                        cluster_id=cluster.id,
                        slide_id=schema.representative_slide_id,
                    )
                )

        # Unparseable elements on representatives.
        by_id = {s.slide_id: s for s in presentation.slides}
        for cluster in induction.clusters:
            slide = by_id.get(cluster.representative_slide_id)
            if slide is None:
                continue
            if slide.parse_warnings:
                blockers.append(
                    SchemaPublishBlocker(
                        code="UNPARSEABLE_ELEMENTS",
                        message="代表页存在无法解析元素："
                        + "; ".join(slide.parse_warnings[:3]),
                        cluster_id=cluster.id,
                        slide_id=slide.slide_id,
                    )
                )
            if not slide.elements:
                warnings.append(f"{slide.slide_id} 无可用元素，填测可能失败")

        # Low-confidence classifications still open.
        open_review = [
            sid
            for sid in induction.low_confidence_slide_ids
            if any(
                c.slide_id == sid and c.needs_review for c in induction.classifications
            )
        ]
        if open_review:
            warnings.append(
                f"仍有 {len(open_review)} 页功能分类待复核（不阻塞 Schema 发布，但建议先修正）"
            )

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
        )
