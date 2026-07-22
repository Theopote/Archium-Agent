"""Template induction pipeline: parse → classify → cluster → representatives → export."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import UTC
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from archium.application.visual.architectural_content_schema_extractor import (
    ArchitecturalContentSchemaExtractor,
)
from archium.application.visual.architectural_content_schema_publish_gate import (
    ArchitecturalContentSchemaPublishGate,
)
from archium.application.visual.asset_path_resolver import is_machine_absolute_path
from archium.application.visual.functional_slide_classifier import FunctionalSlideClassifier
from archium.application.visual.induction_architectural_template_publisher import (
    InductionArchitecturalTemplatePublisher,
    InductionTemplatePublishResult,
)
from archium.application.visual.induction_cluster_editor import rebuild_clusters
from archium.application.visual.outline_template_co_planning_service import (
    OutlineTemplateCoPlanningService,
)
from archium.application.visual.outline_template_editing_service import (
    OutlineTemplateEditingService,
)
from archium.application.visual.reference_slide_clusterer import ReferenceSlideClusterer
from archium.application.visual.representative_slide_selector import RepresentativeSlideSelector
from archium.application.visual.visual_layout_pattern_classifier import (
    VisualLayoutPatternClassifier,
)
from archium.config.settings import Settings, get_settings
from archium.domain.asset import Asset
from archium.domain.outline import OutlinePlan
from archium.domain.presentation import Storyline
from archium.domain.presentation_manuscript import PresentationManuscript
from archium.domain.visual.architectural_content_schema import (
    ArchitecturalContentSchema,
    SchemaPublishReport,
    SchemaReviewOverride,
)
from archium.domain.visual.architectural_template import ArchitecturalTemplate
from archium.domain.visual.design_system import DesignSystem
from archium.domain.visual.reference_slide import ReferencePresentation
from archium.domain.visual.template_induction import (
    InductionReviewOverride,
    OutlineTemplateCoPlan,
    OutlineTemplateEditingBatch,
    TemplateInductionResult,
    TemplateInductionStatus,
)
from archium.exceptions import WorkflowError
from archium.infrastructure.template.reference_pptx_parser import ReferencePptxParser


@dataclass(frozen=True)
class TemplateInductionRunResult:
    induction: TemplateInductionResult
    presentation: ReferencePresentation
    workspace: Path
    artifact_paths: dict[str, Path]
    screenshot_count: int = 0
    screenshot_tools_available: bool = False
    schemas: tuple[ArchitecturalContentSchema, ...] = ()
    publish_report: SchemaPublishReport | None = None


@dataclass(frozen=True)
class TemplateEditingContextBundle:
    """Project-scoped inputs for Phase 6 per-page SlideGenerationContext."""

    project_id: UUID
    manuscript: PresentationManuscript | None = None
    storyline: Storyline | None = None
    assets: tuple[Asset, ...] = ()


class TemplateInductionService:
    """Phase 0–5 induction: parse → classify → cluster → schema → co-plan → publish gate."""

    @staticmethod
    def _representative_classification_unconfirmed(
        induction: TemplateInductionResult,
    ) -> bool:
        for cluster in induction.clusters:
            if not cluster.representative_slide_id:
                continue
            classification = induction.classification_for(cluster.representative_slide_id)
            if classification is not None and classification.needs_review:
                return True
        return False

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        parser: ReferencePptxParser | None = None,
        classifier: FunctionalSlideClassifier | None = None,
        clusterer: ReferenceSlideClusterer | None = None,
        selector: RepresentativeSlideSelector | None = None,
        schema_extractor: ArchitecturalContentSchemaExtractor | None = None,
        publish_gate: ArchitecturalContentSchemaPublishGate | None = None,
        co_planner: OutlineTemplateCoPlanningService | None = None,
        template_editor: OutlineTemplateEditingService | None = None,
        visual_layout_classifier: VisualLayoutPatternClassifier | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._parser = parser or ReferencePptxParser()
        self._classifier = classifier or FunctionalSlideClassifier()
        if clusterer is None:
            self._clusterer = ReferenceSlideClusterer(
                blend_screenshot_embedding=self._settings.induction_screenshot_clustering_enabled,
                screenshot_blend_weight=self._settings.induction_screenshot_clustering_weight,
            )
        else:
            self._clusterer = clusterer
        self._selector = selector or RepresentativeSlideSelector()
        self._schema_extractor = schema_extractor or ArchitecturalContentSchemaExtractor()
        self._publish_gate = publish_gate or ArchitecturalContentSchemaPublishGate()
        self._co_planner = co_planner or OutlineTemplateCoPlanningService()
        self._template_editor = template_editor or OutlineTemplateEditingService()
        self._visual_layout_classifier = (
            visual_layout_classifier or VisualLayoutPatternClassifier()
        )

    def workspace_root(self, induction_id: UUID | str) -> Path:
        path = self._settings.output_path / "template-induction" / str(induction_id)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def induce(
        self,
        pptx_path: Path | str,
        *,
        name: str | None = None,
        induction_id: UUID | None = None,
        capture_screenshots: bool = True,
        require_screenshots: bool = False,
    ) -> TemplateInductionRunResult:
        from archium.infrastructure.renderers.pptx_screenshot import screenshot_tools_available

        source = Path(pptx_path)
        if not source.is_file():
            raise WorkflowError(f"参考 PPTX 不存在：{source}")
        if source.suffix.lower() not in {".pptx", ".pptm"}:
            raise WorkflowError("仅支持 .pptx / .pptm 参考文件。")

        run_id = induction_id or uuid4()
        workspace = Path(self.workspace_root(run_id))
        workspace.mkdir(parents=True, exist_ok=True)
        stored = workspace / "source.pptx"
        shutil.copy2(source, stored)

        tools_ok = screenshot_tools_available()
        presentation = self._parser.parse(
            stored,
            workspace_dir=workspace,
            name=name or source.stem,
            capture_screenshots=capture_screenshots,
        )
        # Ensure slide_count matches PPTX slides even if some pages failed soft.
        presentation.slide_count = len(presentation.slides)

        screenshot_count = self._count_slide_screenshots(workspace, presentation)
        if capture_screenshots:
            presentation.warnings.extend(
                self._screenshot_gap_warnings(
                    presentation,
                    workspace=workspace,
                    tools_available=tools_ok,
                    screenshot_count=screenshot_count,
                )
            )
        if require_screenshots:
            self._require_complete_screenshots(
                presentation,
                workspace=workspace,
                tools_available=tools_ok,
                screenshot_count=screenshot_count,
            )

        classifications = self._classifier.classify_all(presentation.slides)
        classifications = self._visual_layout_classifier.classify_all(
            presentation.slides,
            classifications,
        )
        clusters = self._clusterer.cluster(presentation.slides, classifications)
        clusters, scores = self._selector.select_for_clusters(clusters, presentation.slides)

        low_confidence = [
            c.slide_id for c in classifications if c.needs_review or c.confidence < 0.55
        ]
        induction = TemplateInductionResult(
            id=run_id,
            name=presentation.name,
            workspace_relative=f"template-induction/{run_id}",
            source_filename=source.name,
            slide_count=presentation.slide_count,
            status=TemplateInductionStatus.REVIEW
            if low_confidence
            else TemplateInductionStatus.DRAFT,
            classifications=classifications,
            clusters=clusters,
            representative_scores=scores,
            warnings=list(presentation.warnings),
            low_confidence_slide_ids=low_confidence,
        )

        schemas = self._schema_extractor.extract_for_induction(presentation, induction)
        publish_report = self._publish_gate.evaluate(
            induction=induction,
            presentation=presentation,
            schemas=schemas,
        )
        induction.content_schemas = [s.model_dump(mode="json") for s in schemas]
        induction.publish_report = publish_report.model_dump(mode="json")
        if (
            publish_report.can_publish
            and not self._representative_classification_unconfirmed(induction)
        ):
            induction.status = TemplateInductionStatus.READY

        artifact_paths = self.export_artifacts(
            workspace, presentation, induction, schemas=schemas, publish_report=publish_report
        )
        self._assert_no_absolute_paths(workspace)
        return TemplateInductionRunResult(
            induction=induction,
            presentation=presentation,
            workspace=workspace,
            artifact_paths=artifact_paths,
            screenshot_count=screenshot_count,
            screenshot_tools_available=tools_ok,
            schemas=tuple(schemas),
            publish_report=publish_report,
        )

    @staticmethod
    def _count_slide_screenshots(
        workspace: Path, presentation: ReferencePresentation
    ) -> int:
        count = 0
        for slide in presentation.slides:
            if not slide.image_path:
                continue
            if (workspace / slide.image_path).is_file():
                count += 1
        return count

    @staticmethod
    def _screenshot_gap_warnings(
        presentation: ReferencePresentation,
        *,
        workspace: Path,
        tools_available: bool,
        screenshot_count: int,
    ) -> list[str]:
        warnings: list[str] = []
        if not tools_available:
            warnings.append(
                "截图工具不可用（需 LibreOffice+pdftoppm 或 Windows PowerPoint）；"
                "页面 PNG 未生成，Review UI 将无预览图。"
            )
            return warnings
        missing = [
            slide.slide_id
            for slide in presentation.slides
            if not slide.image_path or not (workspace / slide.image_path).is_file()
        ]
        if missing:
            warnings.append(
                f"截图工具可用但缺失 {len(missing)}/{len(presentation.slides)} 页 PNG："
                + ", ".join(missing[:8])
            )
        elif screenshot_count != presentation.slide_count:
            warnings.append(
                f"截图数量与页数不一致：png={screenshot_count} slides={presentation.slide_count}"
            )
        return warnings

    @staticmethod
    def _require_complete_screenshots(
        presentation: ReferencePresentation,
        *,
        workspace: Path,
        tools_available: bool,
        screenshot_count: int,
    ) -> None:
        if not tools_available:
            raise WorkflowError(
                "require_screenshots=True 但截图工具不可用"
                "（需要 LibreOffice+pdftoppm 或 Windows PowerPoint）。"
            )
        missing = [
            slide.slide_id
            for slide in presentation.slides
            if not slide.image_path or not (workspace / slide.image_path).is_file()
        ]
        if missing:
            raise WorkflowError(
                "页面截图不完整，无法满足验收："
                + ", ".join(missing[:12])
            )
        if screenshot_count != presentation.slide_count:
            raise WorkflowError(
                f"截图数量与页数不一致：png={screenshot_count} slides={presentation.slide_count}"
            )

    def apply_overrides(
        self,
        induction: TemplateInductionResult,
        presentation: ReferencePresentation,
        overrides: list[InductionReviewOverride],
        *,
        cluster_layout: dict[str, list[str]] | None = None,
    ) -> TemplateInductionResult:
        """Apply human corrections (type / cluster / representative) — not numeric scores."""
        class_by_id = {c.slide_id: c for c in induction.classifications}
        type_changed = False
        for override in overrides:
            clf = class_by_id.get(override.slide_id)
            if clf is None:
                continue
            if override.functional_type is not None and override.functional_type != clf.functional_type:
                clf.functional_type = override.functional_type
                clf.needs_review = False
                clf.evidence = [*clf.evidence, "human override: functional_type"]
                type_changed = True
            if override.content_type is not None and override.content_type != clf.content_type:
                clf.content_type = override.content_type
                clf.evidence = [*clf.evidence, "human override: content_type"]
                type_changed = True
            if override.visual_layout_pattern is not None:
                clf.visual_layout_pattern = override.visual_layout_pattern
                clf.evidence = [*clf.evidence, "human override: visual_layout_pattern"]
            if override.is_representative and override.cluster_id:
                for cluster in induction.clusters:
                    if cluster.id == override.cluster_id:
                        cluster.representative_slide_id = override.slide_id
                        cluster.selection_rationale = [
                            "human selected representative",
                            *([override.notes] if override.notes else []),
                        ]
        induction.overrides = list(overrides)
        induction.classifications = list(class_by_id.values())

        if cluster_layout is not None:
            clusters = rebuild_clusters(
                cluster_layout,
                induction.clusters,
                induction.classifications,
            )
            clusters, scores = self._selector.select_for_clusters(
                clusters, presentation.slides
            )
        elif type_changed:
            induction.classifications = self._visual_layout_classifier.classify_all(
                presentation.slides,
                induction.classifications,
            )
            clusters = self._clusterer.cluster(
                presentation.slides, induction.classifications
            )
            clusters, scores = self._selector.select_for_clusters(
                clusters, presentation.slides
            )
        else:
            clusters = list(induction.clusters)
            _, scores = self._selector.select_for_clusters(
                clusters, presentation.slides
            )

        for override in overrides:
            if override.is_representative and override.cluster_id:
                for cluster in clusters:
                    if cluster.id == override.cluster_id or override.slide_id in cluster.slide_ids:
                        cluster.representative_slide_id = override.slide_id
                        cluster.selection_rationale = [
                            "human selected representative",
                            *([override.notes] if override.notes else []),
                        ]
        induction.clusters = clusters
        induction.representative_scores = scores
        induction.low_confidence_slide_ids = [
            c.slide_id for c in induction.classifications if c.needs_review
        ]
        schemas = self._schema_extractor.extract_for_induction(presentation, induction)
        # Preserve human schema corrections by schema cluster id when present.
        previous = {
            str(item.get("cluster_id")): item
            for item in induction.content_schemas
            if isinstance(item, dict) and item.get("human_corrected")
        }
        for schema in schemas:
            prior = previous.get(schema.cluster_id)
            if prior:
                schema.human_corrected = True
                schema.needs_review = False
                if prior.get("page_purpose"):
                    schema.page_purpose = str(prior["page_purpose"])
        report = self._publish_gate.evaluate(
            induction=induction, presentation=presentation, schemas=schemas
        )
        induction.content_schemas = [s.model_dump(mode="json") for s in schemas]
        induction.publish_report = report.model_dump(mode="json")
        induction.status = (
            TemplateInductionStatus.REVIEW
            if self._representative_classification_unconfirmed(induction)
            or not report.can_publish
            else TemplateInductionStatus.READY
        )
        induction.touch()
        return induction

    def apply_schema_overrides(
        self,
        induction: TemplateInductionResult,
        presentation: ReferencePresentation,
        overrides: list[SchemaReviewOverride],
    ) -> tuple[TemplateInductionResult, list[ArchitecturalContentSchema], SchemaPublishReport]:
        schemas = [
            ArchitecturalContentSchema.model_validate(item)
            for item in induction.content_schemas
        ]
        by_id = {s.id: s for s in schemas}
        for override in overrides:
            schema = by_id.get(override.schema_id)
            if schema is None:
                continue
            if override.page_purpose is not None:
                schema.page_purpose = override.page_purpose.strip() or schema.page_purpose
            if override.central_claim_required is not None:
                schema.central_claim_required = override.central_claim_required
            if override.supports_drawing is not None:
                schema.supports_drawing = override.supports_drawing
            if override.citation_required is not None:
                schema.citation_required = override.citation_required
            if override.caption_required is not None:
                schema.caption_required = override.caption_required
            if override.allowed_asset_origins is not None:
                schema.allowed_asset_origins = list(override.allowed_asset_origins)
            if override.forbidden_asset_origins is not None:
                schema.forbidden_asset_origins = list(override.forbidden_asset_origins)
            if "reference_template" not in schema.forbidden_asset_origins:
                schema.forbidden_asset_origins = [
                    *schema.forbidden_asset_origins,
                    "reference_template",
                ]
            schema.human_corrected = True
            schema.needs_review = False
            if override.notes:
                schema.extraction_evidence = [
                    *schema.extraction_evidence,
                    f"human:{override.notes}",
                ]
            schema.touch()

        report = self._publish_gate.evaluate(
            induction=induction, presentation=presentation, schemas=schemas
        )
        induction.content_schemas = [s.model_dump(mode="json") for s in schemas]
        induction.publish_report = report.model_dump(mode="json")
        if report.can_publish:
            induction.status = TemplateInductionStatus.READY
        else:
            induction.status = TemplateInductionStatus.REVIEW
        induction.touch()
        return induction, schemas, report

    def publish(
        self,
        induction: TemplateInductionResult,
        presentation: ReferencePresentation,
        *,
        schemas: list[ArchitecturalContentSchema] | None = None,
    ) -> SchemaPublishReport:
        schema_list = schemas or [
            ArchitecturalContentSchema.model_validate(item)
            for item in induction.content_schemas
        ]
        report = self._publish_gate.evaluate(
            induction=induction,
            presentation=presentation,
            schemas=schema_list,
            formal_publish=True,
        )
        induction.publish_report = report.model_dump(mode="json")
        if report.can_formally_publish:
            induction.status = TemplateInductionStatus.PUBLISHED
            induction.touch()
        return report

    def materialize_architectural_template(
        self,
        induction: TemplateInductionResult,
        presentation: ReferencePresentation,
        workspace: Path,
        *,
        schemas: list[ArchitecturalContentSchema] | None = None,
        source_pptx: Path | None = None,
        session: Session | None = None,
        project_id: UUID | None = None,
    ) -> InductionTemplatePublishResult:
        """Write architectural_template.json (+ optional DB persist) from published induction."""
        if induction.status != TemplateInductionStatus.PUBLISHED:
            raise WorkflowError("请先完成 Schema 正式发布（status=published）。")
        schema_list = schemas or [
            ArchitecturalContentSchema.model_validate(item)
            for item in induction.content_schemas
        ]
        publisher = InductionArchitecturalTemplatePublisher()
        if session is not None:
            result = publisher.publish_to_database(
                session,
                induction=induction,
                presentation=presentation,
                schemas=schema_list,
                workspace=workspace,
                source_pptx=source_pptx,
                project_id=project_id,
            )
        else:
            result = publisher.publish_to_workspace(
                induction=induction,
                presentation=presentation,
                schemas=schema_list,
                workspace=workspace,
                source_pptx=source_pptx,
            )
        self.export_artifacts(workspace, presentation, induction, schemas=schema_list)
        return result

    def record_phase35_signoff(
        self,
        induction: TemplateInductionResult,
        *,
        status: str,
        reviewer: str,
        notes: str = "",
        run_reference: str = "",
        workspace: Path | None = None,
        presentation: ReferencePresentation | None = None,
    ) -> TemplateInductionResult:
        from datetime import datetime

        from archium.domain.visual.template_induction import Phase35HumanSignoff

        induction.phase35_signoff = Phase35HumanSignoff(
            status=status,  # type: ignore[arg-type]
            reviewer=reviewer.strip(),
            notes=notes.strip(),
            run_reference=run_reference.strip(),
            signed_at=datetime.now(UTC),
        )
        induction.touch()
        if workspace is not None and presentation is not None:
            schemas = [
                ArchitecturalContentSchema.model_validate(item)
                for item in induction.content_schemas
            ]
            report = self._publish_gate.evaluate(
                induction=induction,
                presentation=presentation,
                schemas=schemas,
                formal_publish=True,
            )
            induction.publish_report = report.model_dump(mode="json")
            self.export_artifacts(
                workspace,
                presentation,
                induction,
                schemas=schemas,
                publish_report=report,
            )
            signoff_path = workspace / "phase35_human_signoff.json"
            signoff_path.write_text(
                json.dumps(
                    induction.phase35_signoff.model_dump(mode="json"),
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        return induction

    def co_plan_outline(
        self,
        induction: TemplateInductionResult,
        outline: OutlinePlan,
        *,
        schemas: list[ArchitecturalContentSchema] | None = None,
        template: ArchitecturalTemplate | None = None,
        workspace: Path | None = None,
    ) -> OutlineTemplateCoPlan:
        """Phase 5: map outline sections onto induced schemas (+ optional template layouts)."""
        schema_list = schemas or [
            ArchitecturalContentSchema.model_validate(item)
            for item in induction.content_schemas
        ]
        co_plan = self._co_planner.plan(
            outline,
            schema_list,
            template=template,
            induction_id=induction.id,
        )
        if workspace is not None:
            workspace.mkdir(parents=True, exist_ok=True)
            co_plan_path = workspace / "outline_template_co_plan.json"
            co_plan_path.write_text(
                json.dumps(co_plan.model_dump(mode="json"), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            outline_path = workspace / "outline_plan.json"
            outline_path.write_text(
                json.dumps(outline.model_dump(mode="json"), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        return co_plan

    def load_outline_plan(self, workspace: Path) -> OutlinePlan | None:
        path = workspace / "outline_plan.json"
        if not path.is_file():
            return None
        return OutlinePlan.model_validate(json.loads(path.read_text(encoding="utf-8")))

    def load_co_plan(self, workspace: Path) -> OutlineTemplateCoPlan | None:
        path = workspace / "outline_template_co_plan.json"
        if not path.is_file():
            return None
        return OutlineTemplateCoPlan.model_validate(
            json.loads(path.read_text(encoding="utf-8"))
        )

    def load_template_editing_batch(
        self, workspace: Path
    ) -> OutlineTemplateEditingBatch | None:
        path = workspace / "outline_template_editing_batch.json"
        if not path.is_file():
            return None
        return OutlineTemplateEditingBatch.model_validate(
            json.loads(path.read_text(encoding="utf-8"))
        )

    def resolve_template_editing_context(
        self,
        session: Session,
        outline: OutlinePlan,
    ) -> TemplateEditingContextBundle | None:
        """Load manuscript/storyline/assets when outline.presentation_id exists in DB."""
        from archium.application.review_service import PresentationReviewService
        from archium.infrastructure.database.repositories import (
            AssetRepository,
            PresentationRepository,
        )

        presentation = PresentationRepository(session).get_presentation(outline.presentation_id)
        if presentation is None:
            return None

        review_context = PresentationReviewService(session).get_review_context(
            outline.presentation_id
        )
        assets = AssetRepository(session).list_by_project(presentation.project_id)
        return TemplateEditingContextBundle(
            project_id=presentation.project_id,
            manuscript=review_context.manuscript if review_context else None,
            storyline=review_context.storyline if review_context else None,
            assets=tuple(assets),
        )

    def bind_outline_to_presentation(
        self,
        workspace: Path,
        presentation_id: UUID,
    ) -> OutlinePlan:
        """Persist presentation_id on workspace outline_plan.json for Phase 6 context."""
        outline = self.load_outline_plan(workspace)
        if outline is None:
            raise WorkflowError("缺少 outline_plan.json，请先生成协同规划。")
        updated = outline.model_copy(update={"presentation_id": presentation_id})
        path = workspace / "outline_plan.json"
        path.write_text(
            json.dumps(updated.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return updated

    def execute_co_plan_template_editing(
        self,
        induction: TemplateInductionResult,
        outline: OutlinePlan,
        co_plan: OutlineTemplateCoPlan,
        presentation: ReferencePresentation,
        *,
        schemas: list[ArchitecturalContentSchema] | None = None,
        template: ArchitecturalTemplate | None = None,
        assets: list[Asset] | None = None,
        design_system: DesignSystem | None = None,
        workspace: Path | None = None,
        session: Session | None = None,
        project_id: UUID | None = None,
        manuscript: PresentationManuscript | None = None,
        storyline: Storyline | None = None,
    ) -> tuple[OutlineTemplateEditingBatch, OutlineTemplateCoPlan]:
        """Phase 6: materialize RenderScenes for co-plan ``template_editing`` pages."""
        schema_list = schemas or [
            ArchitecturalContentSchema.model_validate(item)
            for item in induction.content_schemas
        ]
        arch_template = template
        if arch_template is None and workspace is not None:
            arch_template = self.load_architectural_template(workspace)
        if arch_template is None:
            raise WorkflowError(
                "缺少 architectural_template.json，请先 materialize 归纳模板后再执行 template_editing。"
            )

        resolved_assets = list(assets) if assets is not None else None
        if session is not None:
            bundle = self.resolve_template_editing_context(session, outline)
            if bundle is not None:
                project_id = project_id or bundle.project_id
                manuscript = manuscript or bundle.manuscript
                storyline = storyline or bundle.storyline
                if resolved_assets is None:
                    resolved_assets = list(bundle.assets)

        batch, updated_co_plan = self._template_editor.execute(
            co_plan=co_plan,
            outline=outline,
            presentation=presentation,
            schemas=schema_list,
            template=arch_template,
            assets=resolved_assets,
            design_system=design_system,
            workspace=workspace,
            session=session,
            project_id=project_id,
            manuscript=manuscript,
            storyline=storyline,
        )
        if workspace is not None:
            self.export_artifacts(
                workspace,
                presentation,
                induction,
                schemas=schema_list,
                co_plan=updated_co_plan,
                editing_batch=batch,
            )
        return batch, updated_co_plan

    def export_artifacts(
        self,
        workspace: Path,
        presentation: ReferencePresentation,
        induction: TemplateInductionResult,
        *,
        schemas: list[ArchitecturalContentSchema] | None = None,
        publish_report: SchemaPublishReport | None = None,
        co_plan: OutlineTemplateCoPlan | None = None,
        editing_batch: OutlineTemplateEditingBatch | None = None,
    ) -> dict[str, Path]:
        slides_dir = workspace / "slides"
        slides_dir.mkdir(parents=True, exist_ok=True)

        for slide in presentation.slides:
            slide_json = slides_dir / f"{slide.slide_id}.json"
            slide_json.write_text(
                json.dumps(slide.model_dump(mode="json"), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

        ref_path = workspace / "reference_presentation.json"
        ref_path.write_text(
            json.dumps(presentation.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        functional_path = workspace / "functional_classification.json"
        functional_path.write_text(
            json.dumps(
                [c.model_dump(mode="json") for c in induction.classifications],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        clusters_path = workspace / "content_clusters.json"
        clusters_path.write_text(
            json.dumps(
                [c.model_dump(mode="json") for c in induction.clusters],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        reps = []
        for cluster in induction.clusters:
            reps.append(
                {
                    "cluster_id": cluster.id,
                    "representative_slide_id": cluster.representative_slide_id,
                    "functional_type": cluster.functional_type.value,
                    "content_type": cluster.content_type.value,
                    "slide_ids": cluster.slide_ids,
                    "selection_rationale": cluster.selection_rationale,
                    "confidence": cluster.confidence,
                }
            )
        reps_path = workspace / "representative_slides.json"
        reps_path.write_text(
            json.dumps(reps, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        schema_list = schemas or [
            ArchitecturalContentSchema.model_validate(item)
            for item in induction.content_schemas
        ]
        schemas_path = workspace / "content_schemas.json"
        schemas_path.write_text(
            json.dumps(
                [s.model_dump(mode="json") for s in schema_list],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        report = publish_report
        if report is None and induction.publish_report:
            report = SchemaPublishReport.model_validate(induction.publish_report)
        if report is not None:
            publish_path = workspace / "schema_publish_report.json"
            publish_path.write_text(
                json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        else:
            publish_path = workspace / "schema_publish_report.json"

        induction_path = workspace / "induction_result.json"
        induction_path.write_text(
            json.dumps(induction.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        paths: dict[str, Path] = {
            "reference_presentation": ref_path,
            "functional_classification": functional_path,
            "content_clusters": clusters_path,
            "representative_slides": reps_path,
            "content_schemas": schemas_path,
            "schema_publish_report": publish_path,
            "induction_result": induction_path,
            "slides_dir": slides_dir,
        }

        outline_path = workspace / "outline_plan.json"
        if outline_path.is_file():
            paths["outline_plan"] = outline_path

        if co_plan is not None:
            co_plan_path = workspace / "outline_template_co_plan.json"
            co_plan_path.write_text(
                json.dumps(co_plan.model_dump(mode="json"), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            paths["outline_template_co_plan"] = co_plan_path

        if editing_batch is not None:
            batch_path = workspace / "outline_template_editing_batch.json"
            batch_path.write_text(
                json.dumps(editing_batch.model_dump(mode="json"), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            paths["outline_template_editing_batch"] = batch_path

        template_path = workspace / "architectural_template.json"
        if template_path.is_file():
            paths["architectural_template"] = template_path
            from archium.application.visual.template_usage_brief_service import (
                TemplateUsageBriefService,
            )

            template = ArchitecturalTemplate.model_validate(
                json.loads(template_path.read_text(encoding="utf-8"))
            )
            _, brief_paths = TemplateUsageBriefService().write_for_template(
                workspace, template, induction=induction
            )
            paths.update(brief_paths)

        return paths

    def load_architectural_template(self, workspace: Path) -> ArchitecturalTemplate | None:
        path = workspace / "architectural_template.json"
        if not path.is_file():
            return None
        return ArchitecturalTemplate.model_validate(
            json.loads(path.read_text(encoding="utf-8"))
        )

    def load_workspace(self, workspace: Path) -> tuple[ReferencePresentation, TemplateInductionResult]:
        presentation = ReferencePresentation.model_validate(
            json.loads((workspace / "reference_presentation.json").read_text(encoding="utf-8"))
        )
        induction = TemplateInductionResult.model_validate(
            json.loads((workspace / "induction_result.json").read_text(encoding="utf-8"))
        )
        from archium.application.visual.induction_screenshot_embedding import (
            enrich_slide_screenshot_embeddings,
        )

        slides, attached = enrich_slide_screenshot_embeddings(
            presentation.slides,
            workspace,
            enabled=self._settings.induction_screenshot_clustering_enabled,
        )
        if attached:
            presentation = presentation.model_copy(update={"slides": slides})
        signoff_path = workspace / "phase35_human_signoff.json"
        if signoff_path.is_file() and induction.phase35_signoff is None:
            from archium.domain.visual.template_induction import Phase35HumanSignoff

            induction.phase35_signoff = Phase35HumanSignoff.model_validate(
                json.loads(signoff_path.read_text(encoding="utf-8"))
            )
        return presentation, induction

    def content_cluster_count(self, induction: TemplateInductionResult) -> int:
        return sum(
            1
            for c in induction.clusters
            if c.functional_type.value == "content" and len(c.slide_ids) >= 1
        )

    def _assert_no_absolute_paths(self, workspace: Path) -> None:
        for path in workspace.rglob("*.json"):
            text = path.read_text(encoding="utf-8")
            data = json.loads(text)
            self._walk_forbid_absolute(data, context=str(path.relative_to(workspace)))

    def _walk_forbid_absolute(self, node: object, *, context: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if (
                    key
                    in {
                        "image_path",
                        "relative_path",
                        "source_pptx_relative",
                        "workspace_relative",
                    }
                    and isinstance(value, str)
                    and is_machine_absolute_path(value)
                ):
                    raise WorkflowError(
                        f"绝对路径不得持久化：{context}::{key}={value}"
                    )
                self._walk_forbid_absolute(value, context=context)
        elif isinstance(node, list):
            for item in node:
                self._walk_forbid_absolute(item, context=context)
