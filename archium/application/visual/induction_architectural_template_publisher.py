"""Publish induced template packages as ArchitecturalTemplate (with Content Schemas)."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from archium.domain.visual.architectural_content_schema import ArchitecturalContentSchema
from archium.domain.visual.architectural_template import (
    ArchitecturalTemplate,
    ArchitecturalTemplateLayout,
    TemplatePageType,
    TemplateSlot,
    TemplateSlotRole,
    TemplateStatus,
)
from archium.domain.visual.reference_slide import (
    ReferenceElement,
    ReferenceElementType,
    ReferencePresentation,
    ReferenceSlideSnapshot,
)
from archium.domain.visual.template_induction import (
    ArchitecturalContentType,
    FunctionalSlideType,
    ReferenceSlideCluster,
    TemplateInductionResult,
)
from archium.exceptions import WorkflowError
from archium.infrastructure.database.visual_repositories import ArchitecturalTemplateRepository

_CONTENT_TO_PAGE_TYPE: dict[ArchitecturalContentType, TemplatePageType] = {
    ArchitecturalContentType.COVER_VISUAL: TemplatePageType.COVER,
    ArchitecturalContentType.SECTION_VISUAL: TemplatePageType.SECTION,
    ArchitecturalContentType.DRAWING_FOCUS: TemplatePageType.DRAWING_FOCUS,
    ArchitecturalContentType.PHOTO_ANALYSIS: TemplatePageType.PHOTO_GRID,
    ArchitecturalContentType.CASE_COMPARISON: TemplatePageType.CASE_COMPARISON,
    ArchitecturalContentType.BEFORE_AFTER: TemplatePageType.BEFORE_AFTER,
    ArchitecturalContentType.METRIC_SUMMARY: TemplatePageType.METRIC,
    ArchitecturalContentType.STRATEGY: TemplatePageType.TEXT_ARGUMENT,
    ArchitecturalContentType.PROCESS: TemplatePageType.PROCESS,
    ArchitecturalContentType.TIMELINE: TemplatePageType.TIMELINE,
    ArchitecturalContentType.DIAGRAM: TemplatePageType.DRAWING_FOCUS,
    ArchitecturalContentType.TEXT_ARGUMENT: TemplatePageType.TEXT_ARGUMENT,
    ArchitecturalContentType.IMAGE_TEXT_HYBRID: TemplatePageType.PHOTO_GRID,
    ArchitecturalContentType.MULTI_IMAGE_GRID: TemplatePageType.PHOTO_GRID,
    ArchitecturalContentType.CONCLUSION: TemplatePageType.CLOSING,
    ArchitecturalContentType.UNKNOWN: TemplatePageType.UNKNOWN,
}

_FUNCTIONAL_TO_PAGE_TYPE: dict[FunctionalSlideType, TemplatePageType] = {
    FunctionalSlideType.COVER: TemplatePageType.COVER,
    FunctionalSlideType.AGENDA: TemplatePageType.AGENDA,
    FunctionalSlideType.SECTION_DIVIDER: TemplatePageType.SECTION,
    FunctionalSlideType.EXECUTIVE_SUMMARY: TemplatePageType.TEXT_ARGUMENT,
    FunctionalSlideType.DECISION: TemplatePageType.TEXT_ARGUMENT,
    FunctionalSlideType.CONTENT: TemplatePageType.UNKNOWN,
    FunctionalSlideType.CLOSING: TemplatePageType.CLOSING,
    FunctionalSlideType.APPENDIX: TemplatePageType.UNKNOWN,
    FunctionalSlideType.UNKNOWN: TemplatePageType.UNKNOWN,
}

_SEMANTIC_TO_SLOT: dict[str, TemplateSlotRole] = {
    "title": TemplateSlotRole.TITLE,
    "subtitle": TemplateSlotRole.SUBTITLE,
    "body": TemplateSlotRole.BODY,
    "caption": TemplateSlotRole.CAPTION,
    "source": TemplateSlotRole.SOURCE,
    "metric": TemplateSlotRole.METRIC,
    "drawing": TemplateSlotRole.DRAWING,
    "hero_image": TemplateSlotRole.HERO_IMAGE,
    "hero": TemplateSlotRole.HERO_IMAGE,
    "supporting_image": TemplateSlotRole.SUPPORTING_IMAGE,
    "chart": TemplateSlotRole.CHART,
    "table": TemplateSlotRole.TABLE,
    "placeholder": TemplateSlotRole.BODY,
}


@dataclass(frozen=True)
class InductionTemplatePublishResult:
    template: ArchitecturalTemplate
    artifact_path: Path
    persisted: bool


class InductionArchitecturalTemplatePublisher:
    """Materialize ArchitecturalTemplate from a published induction workspace."""

    def build(
        self,
        *,
        induction: TemplateInductionResult,
        presentation: ReferencePresentation,
        schemas: list[ArchitecturalContentSchema],
        workspace: Path,
        source_pptx: Path | None = None,
        project_id: UUID | None = None,
        template_id: UUID | None = None,
    ) -> ArchitecturalTemplate:
        if induction.status.value != "published":
            raise WorkflowError("归纳状态必须为 published 才能发布 ArchitecturalTemplate。")
        if not schemas:
            raise WorkflowError("缺少 content schemas，无法发布 ArchitecturalTemplate。")

        by_cluster = {s.cluster_id: s for s in schemas if s.cluster_id}
        slides_by_id = {s.slide_id: s for s in presentation.slides}
        layouts: list[ArchitecturalTemplateLayout] = []
        page_index = 0

        for cluster in induction.clusters:
            schema = by_cluster.get(cluster.id)
            rep_id = cluster.representative_slide_id
            if not rep_id:
                continue
            slide = slides_by_id.get(rep_id)
            if slide is None:
                continue

            if schema is not None:
                layout = self._layout_from_schema(
                    schema=schema,
                    cluster=cluster,
                    slide=slide,
                    page_index=page_index,
                    workspace=workspace,
                )
            elif cluster.functional_type != FunctionalSlideType.CONTENT:
                layout = self._layout_from_functional_cluster(
                    cluster=cluster,
                    slide=slide,
                    page_index=page_index,
                    workspace=workspace,
                )
            else:
                continue

            layouts.append(layout)
            page_index += 1

        if not layouts:
            raise WorkflowError("未能从代表页构建任何模板 layout。")

        template_root = workspace / "architectural_template"
        template_root.mkdir(parents=True, exist_ok=True)
        stored_pptx = template_root / "source.pptx"
        if source_pptx and source_pptx.is_file() and not stored_pptx.is_file():
            shutil.copy2(source_pptx, stored_pptx)

        fonts = sorted({f for slide in presentation.slides for f in slide.fonts})
        colors = sorted({c for slide in presentation.slides for c in slide.colors})

        return ArchitecturalTemplate(
            id=template_id or uuid4(),
            name=induction.name,
            source_pptx_path=str(stored_pptx.relative_to(workspace)) if stored_pptx.is_file() else "",
            project_id=project_id,
            fonts=[],
            colors=colors[:16],
            layouts=layouts,
            status=TemplateStatus.PUBLISHED,
            workspace_dir=str(workspace),
            analysis_notes=[
                "published_from_template_induction",
                f"induction_id={induction.id}",
                f"schema_count={len(schemas)}",
                f"layout_count={len(layouts)}",
                f"extracted_fonts={','.join(fonts[:12])}" if fonts else "extracted_fonts=",
            ],
            induction_id=str(induction.id),
            induction_workspace_relative=induction.workspace_relative,
            content_schemas=list(schemas),
        )

    def publish_to_workspace(
        self,
        *,
        induction: TemplateInductionResult,
        presentation: ReferencePresentation,
        schemas: list[ArchitecturalContentSchema],
        workspace: Path,
        source_pptx: Path | None = None,
    ) -> InductionTemplatePublishResult:
        template = self.build(
            induction=induction,
            presentation=presentation,
            schemas=schemas,
            workspace=workspace,
            source_pptx=source_pptx,
        )
        artifact = workspace / "architectural_template.json"
        artifact.write_text(
            json.dumps(template.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        induction.architectural_template_id = str(template.id)
        induction_path = workspace / "induction_result.json"
        induction_path.write_text(
            json.dumps(induction.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return InductionTemplatePublishResult(
            template=template, artifact_path=artifact, persisted=False
        )

    def publish_to_database(
        self,
        session: Session,
        *,
        induction: TemplateInductionResult,
        presentation: ReferencePresentation,
        schemas: list[ArchitecturalContentSchema],
        workspace: Path,
        source_pptx: Path | None = None,
        project_id: UUID | None = None,
    ) -> InductionTemplatePublishResult:
        result = self.publish_to_workspace(
            induction=induction,
            presentation=presentation,
            schemas=schemas,
            workspace=workspace,
            source_pptx=source_pptx,
        )
        repo = ArchitecturalTemplateRepository(session)
        saved = repo.save(result.template.model_copy(update={"project_id": project_id}))
        session.commit()
        return InductionTemplatePublishResult(
            template=saved,
            artifact_path=result.artifact_path,
            persisted=True,
        )

    def _layout_from_schema(
        self,
        *,
        schema: ArchitecturalContentSchema,
        cluster: ReferenceSlideCluster,
        slide: ReferenceSlideSnapshot,
        page_index: int,
        workspace: Path,
    ) -> ArchitecturalTemplateLayout:
        page_type = _CONTENT_TO_PAGE_TYPE.get(
            schema.content_type, TemplatePageType.UNKNOWN
        )
        slots = self._slots_from_slide(slide, schema=schema)
        preview = self._preview_path(slide, workspace)
        return ArchitecturalTemplateLayout(
            name=schema.name,
            description=schema.page_purpose,
            page_index=page_index,
            page_type=page_type,
            suitable_slide_types=[schema.functional_type.value],
            suitable_content_types=[schema.content_type.value],
            architectural_roles=sorted(schema.required_roles()),
            slots=slots,
            supports_drawing=schema.supports_drawing,
            supports_photo=schema.has_image_slot(),
            supports_before_after=schema.content_type
            == ArchitecturalContentType.BEFORE_AFTER,
            supports_metrics=schema.content_type == ArchitecturalContentType.METRIC_SUMMARY
            or bool(schema.required_roles() & {"metric"}),
            supports_case_reference=schema.content_type
            == ArchitecturalContentType.CASE_COMPARISON,
            minimum_asset_count=schema.min_asset_count,
            maximum_asset_count=schema.max_asset_count,
            minimum_text_length=schema.min_text_length,
            maximum_text_length=schema.max_text_length,
            preview_image_path=preview,
            page_width=slide.width,
            page_height=slide.height,
            extracted_fonts=list(slide.fonts),
            extracted_colors=list(slide.colors),
            classification_confidence=schema.confidence,
            classification_notes="; ".join(schema.extraction_evidence[:4]),
            content_schema_id=schema.id,
            cluster_id=cluster.id,
            representative_slide_id=slide.slide_id,
        )

    def _layout_from_functional_cluster(
        self,
        *,
        cluster: ReferenceSlideCluster,
        slide: ReferenceSlideSnapshot,
        page_index: int,
        workspace: Path,
    ) -> ArchitecturalTemplateLayout:
        page_type = _FUNCTIONAL_TO_PAGE_TYPE.get(
            cluster.functional_type, TemplatePageType.UNKNOWN
        )
        slots = self._slots_from_slide(slide, schema=None)
        preview = self._preview_path(slide, workspace)
        return ArchitecturalTemplateLayout(
            name=f"{cluster.functional_type.value}/{cluster.content_type.value}",
            description=f"Functional page — {cluster.functional_type.value}",
            page_index=page_index,
            page_type=page_type,
            suitable_slide_types=[cluster.functional_type.value],
            suitable_content_types=[cluster.content_type.value],
            slots=slots,
            preview_image_path=preview,
            page_width=slide.width,
            page_height=slide.height,
            extracted_fonts=list(slide.fonts),
            extracted_colors=list(slide.colors),
            cluster_id=cluster.id,
            representative_slide_id=slide.slide_id,
        )

    def _slots_from_slide(
        self,
        slide: ReferenceSlideSnapshot,
        *,
        schema: ArchitecturalContentSchema | None,
    ) -> list[TemplateSlot]:
        slots: list[TemplateSlot] = []
        seq = 0
        for element in slide.iter_elements():
            slot = self._element_to_slot(element, seq=seq, schema=schema)
            if slot is None:
                continue
            slots.append(slot)
            seq += 1
        return slots

    def _element_to_slot(
        self,
        element: ReferenceElement,
        *,
        seq: int,
        schema: ArchitecturalContentSchema | None,
    ) -> TemplateSlot | None:
        if element.likely_background_or_decoration:
            return None
        if element.element_type == ReferenceElementType.DECORATION:
            return None

        role = _SEMANTIC_TO_SLOT.get((element.semantic_role or "").lower())
        if role is None and element.placeholder_binding is not None:
            role = _SEMANTIC_TO_SLOT.get(
                (element.placeholder_binding.semantic_role or "").lower()
            )
        if role is None:
            if element.element_type == ReferenceElementType.IMAGE:
                role = TemplateSlotRole.SUPPORTING_IMAGE
            elif element.element_type == ReferenceElementType.DRAWING:
                role = TemplateSlotRole.DRAWING
            elif element.element_type == ReferenceElementType.TEXT:
                role = TemplateSlotRole.BODY
            elif element.element_type == ReferenceElementType.PLACEHOLDER:
                # Picture placeholders without upgraded role still become image slots.
                if "placeholder_hosts_picture" in element.style_notes:
                    role = TemplateSlotRole.HERO_IMAGE
                else:
                    role = TemplateSlotRole.BODY
            elif element.element_type == ReferenceElementType.CHART:
                role = TemplateSlotRole.CHART
            elif element.element_type == ReferenceElementType.TABLE:
                role = TemplateSlotRole.TABLE
            else:
                return None

        accepted_origins = list(schema.allowed_asset_origins) if schema else []
        constraints = list(schema.architectural_constraints) if schema else []
        required = False
        if schema is not None:
            required = role.value in schema.required_roles()

        node_types = ["text"]
        if role in {
            TemplateSlotRole.HERO_IMAGE,
            TemplateSlotRole.SUPPORTING_IMAGE,
            TemplateSlotRole.DRAWING,
            TemplateSlotRole.CHART,
        }:
            node_types = ["image", "drawing"] if role == TemplateSlotRole.DRAWING else ["image"]

        crop = "contain" if role == TemplateSlotRole.DRAWING else "none"

        return TemplateSlot(
            id=f"slot_{seq:03d}",
            role=role,
            required=required,
            x=element.x,
            y=element.y,
            width=max(element.width, 0.05),
            height=max(element.height, 0.05),
            accepted_node_types=node_types,
            accepted_asset_origins=accepted_origins,
            accepted_drawing_types=list(schema.allowed_drawing_types) if schema else [],
            architectural_constraints=constraints,
            label=(element.text or "")[:40],
            source_shape_name=element.source_shape_name or element.id,
            auto_detected=True,
            crop_policy=crop,
            placeholder_binding=element.placeholder_binding,
        )

    @staticmethod
    def _preview_path(slide: ReferenceSlideSnapshot, workspace: Path) -> str:
        if not slide.image_path:
            return ""
        candidate = workspace / slide.image_path
        return str(slide.image_path) if candidate.is_file() else slide.image_path
