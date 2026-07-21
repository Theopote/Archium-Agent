"""Execute co-plan ``template_editing`` pages via reference-slide editing (Phase 6)."""

from __future__ import annotations

import json
from pathlib import Path

from archium.application.visual.outline_template_co_planning_service import (
    OutlineTemplateCoPlanningService,
)
from archium.application.visual.reference_slide_editing_service import ReferenceSlideEditingService
from archium.domain.asset import Asset
from archium.domain.outline import OutlinePlan, OutlineSection
from archium.domain.slide import SlideSpec
from archium.domain.visual.architectural_content_schema import ArchitecturalContentSchema
from archium.domain.visual.architectural_template import ArchitecturalTemplate
from archium.domain.visual.defaults import default_presentation_design_system
from archium.domain.visual.design_system import DesignSystem
from archium.domain.visual.reference_slide import ReferencePresentation, ReferenceSlideSnapshot
from archium.domain.visual.template_induction import (
    OutlineTemplateCoPlan,
    OutlineTemplateCompatibility,
    OutlineTemplateEditingBatch,
    TemplateEditingPageResult,
)


class OutlineTemplateEditingService:
    """Materialize RenderScenes for co-plan pages routed to ``template_editing``."""

    def __init__(
        self,
        *,
        editor: ReferenceSlideEditingService | None = None,
        co_planner: OutlineTemplateCoPlanningService | None = None,
    ) -> None:
        self._editor = editor or ReferenceSlideEditingService()
        self._co_planner = co_planner or OutlineTemplateCoPlanningService()

    def execute(
        self,
        *,
        co_plan: OutlineTemplateCoPlan,
        outline: OutlinePlan,
        presentation: ReferencePresentation,
        schemas: list[ArchitecturalContentSchema],
        template: ArchitecturalTemplate,
        assets: list[Asset] | None = None,
        design_system: DesignSystem | None = None,
        workspace: Path | None = None,
    ) -> tuple[OutlineTemplateEditingBatch, OutlineTemplateCoPlan]:
        ds = design_system or default_presentation_design_system()
        project_assets = list(assets or [])
        schema_by_id = {schema.id: schema for schema in schemas}
        section_by_id = {section.id: section for section in outline.sections}
        slide_by_id = {slide.slide_id: slide for slide in presentation.slides}
        layout_by_id = {layout.id: layout for layout in template.layouts}

        page_results: list[TemplateEditingPageResult] = []
        updated_pages: list[OutlineTemplateCompatibility] = []
        batch_warnings: list[str] = []

        editing_pages = [p for p in co_plan.page_plans if p.fallback_mode == "template_editing"]
        if not editing_pages:
            batch_warnings.append("no template_editing pages in co-plan")

        scenes_root = "co_plan_scenes" if workspace is not None else ""

        for page in co_plan.page_plans:
            if page.fallback_mode != "template_editing":
                updated_pages.append(page)
                continue

            section = section_by_id.get(page.section_id)
            if section is None:
                result = self._failed_result(
                    page,
                    error=f"outline section not found: {page.section_id}",
                )
                page_results.append(result)
                updated_pages.append(self._apply_page_status(page, result))
                continue

            schema = schema_by_id.get(page.schema_id or "")
            if schema is None:
                result = self._skipped_result(
                    page,
                    error="no schema bound for template_editing page",
                )
                page_results.append(result)
                updated_pages.append(self._apply_page_status(page, result))
                continue

            rep_slide_id = (
                page.representative_slide_id
                or schema.representative_slide_id
                or ""
            )
            layout = layout_by_id.get(page.preferred_layout_id or "")
            if not rep_slide_id and layout is not None:
                rep_slide_id = layout.representative_slide_id or ""

            reference_slide = slide_by_id.get(rep_slide_id) if rep_slide_id else None
            if reference_slide is None:
                result = self._skipped_result(
                    page,
                    representative_slide_id=rep_slide_id or None,
                    schema_id=schema.id,
                    layout_id=page.preferred_layout_id,
                    error="reference slide snapshot not found",
                )
                page_results.append(result)
                updated_pages.append(self._apply_page_status(page, result))
                continue

            slide_spec = self._slide_spec_for_page(
                outline=outline,
                section=section,
                page=page,
            )
            try:
                edit_result = self._editor.generate_scene(
                    reference_slide=reference_slide,
                    content_schema=schema,
                    slide_spec=slide_spec,
                    assets=project_assets,
                    design_system=ds,
                    template=template,
                    layout_id=page.preferred_layout_id,
                    presentation_id=outline.presentation_id,
                )
            except Exception as exc:  # noqa: BLE001 — batch must continue on single-page failure
                result = self._failed_result(
                    page,
                    schema_id=schema.id,
                    representative_slide_id=rep_slide_id,
                    layout_id=page.preferred_layout_id,
                    error=str(exc),
                )
                page_results.append(result)
                updated_pages.append(self._apply_page_status(page, result))
                continue

            scene_rel = ""
            if workspace is not None:
                scene_rel = f"{scenes_root}/{page.slide_id}/render_scene.json"
                scene_path = workspace / scene_rel
                scene_path.parent.mkdir(parents=True, exist_ok=True)
                scene_path.write_text(
                    json.dumps(edit_result.scene.model_dump(mode="json"), ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )

            result = TemplateEditingPageResult(
                slide_id=page.slide_id,
                section_id=page.section_id,
                schema_id=schema.id,
                representative_slide_id=rep_slide_id,
                layout_id=page.preferred_layout_id,
                status="generated",
                edit_scene_relative_path=scene_rel,
                node_count=len(edit_result.scene.nodes),
                stripped_text_count=edit_result.stripped_text_count,
                stripped_asset_count=edit_result.stripped_asset_count,
                warnings=list(edit_result.warnings),
            )
            page_results.append(result)
            updated_pages.append(self._apply_page_status(page, result))

        updated_co_plan = co_plan.model_copy(update={"page_plans": updated_pages})
        batch = OutlineTemplateEditingBatch(
            co_plan_id=str(co_plan.id),
            outline_id=co_plan.outline_id,
            induction_id=co_plan.induction_id,
            template_id=co_plan.template_id,
            page_results=page_results,
            warnings=batch_warnings,
        )

        if workspace is not None:
            workspace.mkdir(parents=True, exist_ok=True)
            batch_path = workspace / "outline_template_editing_batch.json"
            batch_path.write_text(
                json.dumps(batch.model_dump(mode="json"), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            co_plan_path = workspace / "outline_template_co_plan.json"
            co_plan_path.write_text(
                json.dumps(updated_co_plan.model_dump(mode="json"), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

        return batch, updated_co_plan

    def _slide_spec_for_page(
        self,
        *,
        outline: OutlinePlan,
        section: OutlineSection,
        page: OutlineTemplateCompatibility,
    ) -> SlideSpec:
        message = (section.key_message or section.purpose or section.title).strip()
        if page.page_role == "overflow" and section.purpose.strip():
            message = section.purpose.strip()
        key_points = [
            item.strip()
            for item in [*section.evidence_requirements, section.key_message]
            if item and item.strip()
        ][:5]
        return SlideSpec(
            presentation_id=outline.presentation_id,
            chapter_id=section.id,
            order=page.planned_page_index,
            title=section.title,
            message=message,
            key_points=key_points,
            slide_type=OutlineTemplateCoPlanningService._slide_type_for_functional(
                page.inferred_functional_type,
                page.inferred_content_type,
            ),
        )

    @staticmethod
    def _apply_page_status(
        page: OutlineTemplateCompatibility,
        result: TemplateEditingPageResult,
    ) -> OutlineTemplateCompatibility:
        status = "generated" if result.status == "generated" else result.status
        if result.status == "skipped":
            status = "skipped"
        return page.model_copy(
            update={
                "edit_scene_status": status,
                "edit_scene_relative_path": result.edit_scene_relative_path,
            }
        )

    @staticmethod
    def _skipped_result(
        page: OutlineTemplateCompatibility,
        *,
        schema_id: str | None = None,
        representative_slide_id: str | None = None,
        layout_id: str | None = None,
        error: str = "",
    ) -> TemplateEditingPageResult:
        return TemplateEditingPageResult(
            slide_id=page.slide_id,
            section_id=page.section_id,
            schema_id=schema_id or page.schema_id,
            representative_slide_id=representative_slide_id or page.representative_slide_id,
            layout_id=layout_id or page.preferred_layout_id,
            status="skipped",
            error=error,
        )

    @staticmethod
    def _failed_result(
        page: OutlineTemplateCompatibility,
        *,
        schema_id: str | None = None,
        representative_slide_id: str | None = None,
        layout_id: str | None = None,
        error: str = "",
    ) -> TemplateEditingPageResult:
        return TemplateEditingPageResult(
            slide_id=page.slide_id,
            section_id=page.section_id,
            schema_id=schema_id or page.schema_id,
            representative_slide_id=representative_slide_id or page.representative_slide_id,
            layout_id=layout_id or page.preferred_layout_id,
            status="failed",
            error=error,
        )

    @staticmethod
    def load_reference_slide(
        presentation: ReferencePresentation,
        slide_id: str,
    ) -> ReferenceSlideSnapshot | None:
        for slide in presentation.slides:
            if slide.slide_id == slide_id:
                return slide
        return None
