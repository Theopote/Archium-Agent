"""Slide Recovery Phase 6 — preview, PPTX export, and import into a presentation."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from archium.application.artifact_policy_service import (
    ArtifactMutationOperation,
    save_render_scene,
)
from archium.application.delivery_record_service import DeliveryRecordService
from archium.application.export_policy_service import (
    ExportPolicyService,
    export_policy_from_preset,
)
from archium.application.slide_recovery_workflow_service import SlideRecoveryWorkflowResult
from archium.application.visual.scene_history_service import SceneHistoryService
from archium.application.visual.studio_scene_service import StudioSceneService
from archium.application.visual.template_studio_service import (
    RecoveryTemplateSaveResult,
    TemplateStudioService,
)
from archium.config.settings import Settings, get_settings
from archium.domain.enums import RevisionSource, SlideType
from archium.domain.export_fidelity import DeckExportManifest, ExportPolicy, SlideExportResult
from archium.domain.presentation import Presentation
from archium.domain.slide import SlideSpec, build_slide_logical_key
from archium.domain.slide_recovery import HybridRenderScene, SlideRecoveryResult
from archium.domain.visual.defaults import default_presentation_design_system
from archium.domain.visual.design_system import DesignSystem
from archium.domain.visual.enums import LayoutContentType, LayoutElementRole, LayoutFamily
from archium.domain.visual.layout import LayoutElement, LayoutPlan
from archium.domain.visual.render_scene import RenderScene, TextNode
from archium.exceptions import WorkflowError
from archium.infrastructure.database.repositories import PresentationRepository
from archium.infrastructure.database.visual_repositories import (
    DesignSystemRepository,
    LayoutPlanRepository,
    RenderSceneRepository,
)
from archium.infrastructure.renderers.pptx_renderer import maybe_export_scene_pptx

_RECOVERY_LAYOUT_VARIANT = "recovery_import"
_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}


@dataclass(frozen=True)
class SlideRecoveryExportResult:
    pptx_path: Path | None
    manifest: DeckExportManifest
    slide_export: SlideExportResult
    scene_preview_path: Path | None = None
    pptx_export_skipped: bool = False


@dataclass(frozen=True)
class SlideRecoveryImportResult:
    presentation_id: UUID
    slide_id: UUID
    scene_id: UUID
    revision_id: UUID
    slide_order: int
    scene_preview_path: Path | None = None


class SlideRecoveryDeliveryService:
    """Preview, export, and import recovered hybrid scenes."""

    def __init__(self, session: Session, *, settings: Settings | None = None) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._presentations = PresentationRepository(session)
        self._plans = LayoutPlanRepository(session)
        self._scenes = RenderSceneRepository(session)
        self._designs = DesignSystemRepository(session)
        self._export_policy = ExportPolicyService()
        self._scene_history = SceneHistoryService(session)
        self._studio_scenes = StudioSceneService(session, settings=self._settings)

    def resolve_source_preview_path(
        self,
        result: SlideRecoveryWorkflowResult,
    ) -> Path | None:
        state = dict(result.workflow_run.state or {})
        for key in ("preview_image_path", "source_path"):
            raw = state.get(key)
            if not raw:
                continue
            path = Path(str(raw))
            if path.is_file() and path.suffix.lower() in _IMAGE_SUFFIXES:
                return path
        return None

    def render_hybrid_preview(
        self,
        project_id: UUID,
        hybrid: HybridRenderScene,
        *,
        presentation_id: UUID | None = None,
    ) -> Path:
        target_presentation = presentation_id or uuid4()
        return self._studio_scenes.render_scene_preview(
            target_presentation,
            hybrid.scene,
        )

    def export_pptx(
        self,
        project_id: UUID,
        hybrid: HybridRenderScene,
        *,
        source_page_id: str,
        policy_preset: str = "allow_hybrid",
        policy: ExportPolicy | None = None,
    ) -> SlideRecoveryExportResult:
        scene = hybrid.scene
        active_policy = policy or export_policy_from_preset(policy_preset)
        slide_export = self._export_policy.assess_scene_fidelity(scene)
        export_presentation_id = self._resolve_export_presentation_id(project_id, scene)
        manifest = self._export_policy.build_deck_manifest(
            presentation_id=export_presentation_id,
            export_format="pptx",
            policy=active_policy,
            slide_results=[slide_export],
            qa_status="recovery",
        )
        self._export_policy.enforce_export_policy(manifest, policy=active_policy)

        output_dir = (
            self._settings.output_path
            / "slide-recovery"
            / str(project_id)
        )
        output_dir.mkdir(parents=True, exist_ok=True)
        safe_name = _safe_filename(source_page_id or "recovered-page")
        output_path = output_dir / f"{safe_name}.pptx"

        exported = maybe_export_scene_pptx(
            scene,
            output_path,
            title=f"Recovery · {source_page_id}",
            settings=self._settings,
        )
        pptx_export_skipped = exported is None
        if exported is not None:
            manifest = self._export_policy.build_deck_manifest(
                presentation_id=manifest.presentation_id,
                export_format="pptx",
                policy=active_policy,
                slide_results=[slide_export],
                file_uri=str(exported),
                file_hash=_file_hash(exported),
                qa_status="recovery",
            )
            DeliveryRecordService(self._session).record_export(
                project_id=project_id,
                presentation_id=export_presentation_id,
                format="pptx",
                file_uri=str(exported),
                qa_status="recovery",
            )

        preview_path = self.render_hybrid_preview(project_id, hybrid)
        return SlideRecoveryExportResult(
            pptx_path=exported,
            manifest=manifest,
            slide_export=slide_export,
            scene_preview_path=preview_path,
            pptx_export_skipped=pptx_export_skipped,
        )

    def import_to_presentation(
        self,
        project_id: UUID,
        hybrid: HybridRenderScene,
        recovery: SlideRecoveryResult | None,
        *,
        presentation_id: UUID | None = None,
        slide_title: str | None = None,
    ) -> SlideRecoveryImportResult:
        presentation = self._resolve_presentation(project_id, presentation_id)
        slides = self._presentations.list_slides(presentation.id)
        slide_order = max((slide.order for slide in slides), default=-1) + 1
        source_id = recovery.source_page_id if recovery is not None else hybrid.recovery_source_id
        title = slide_title or f"复活页 · {source_id}"

        slide = SlideSpec(
            presentation_id=presentation.id,
            chapter_id="recovery",
            order=slide_order,
            title=title,
            message=f"由页面复活导入（{hybrid.page_kind.value}）",
            slide_type=SlideType.CONTENT,
            logical_key=build_slide_logical_key("recovery", slide_order),
        )
        slide = self._presentations.save_slide(slide)

        design = self._ensure_default_design_system()
        plan = _layout_plan_from_recovery_scene(slide.id, hybrid.scene, design.id)
        plan = self._plans.save(plan)

        imported_scene = hybrid.scene.model_copy(
            update={
                "id": uuid4(),
                "slide_id": slide.id,
                "presentation_id": presentation.id,
                "layout_plan_id": plan.id,
            }
        )
        saved_scene = save_render_scene(
            self._scenes,
            imported_scene,
            operation=ArtifactMutationOperation.IMPORT_EXTERNAL,
            entrypoint="slide_recovery.import_external_scene",
        )

        slide = self._presentations.save_slide(
            slide.model_copy(update={"layout_plan_id": plan.id})
        )

        revision, _scene_revision = self._scene_history.record_scene(
            slide=slide,
            scene=saved_scene,
            change_source=RevisionSource.IMPORT,
            scene_revision_source="import_recovery",
            note=f"页面复活导入：{source_id}",
            summary=f"导入 {hybrid.fidelity_label_zh()} 混合场景",
            qa_status="recovery",
        )

        preview_path = self._studio_scenes.render_scene_preview(
            presentation.id,
            saved_scene,
        )
        return SlideRecoveryImportResult(
            presentation_id=presentation.id,
            slide_id=slide.id,
            scene_id=saved_scene.id,
            revision_id=revision.id,
            slide_order=slide_order,
            scene_preview_path=preview_path,
        )

    def save_as_template_reference(
        self,
        project_id: UUID,
        hybrid: HybridRenderScene,
        *,
        source_page_id: str,
        source_preview_path: Path | None = None,
        template_name: str | None = None,
    ) -> RecoveryTemplateSaveResult:
        service = TemplateStudioService(self._session, settings=self._settings)
        return service.create_from_recovery_reference(
            project_id=project_id,
            hybrid=hybrid,
            source_page_id=source_page_id,
            source_preview_path=source_preview_path,
            name=template_name,
        )

    def _resolve_export_presentation_id(
        self,
        project_id: UUID,
        scene: RenderScene,
    ) -> UUID:
        if scene.presentation_id is not None:
            presentation = self._presentations.get_presentation(scene.presentation_id)
            if presentation is not None and presentation.project_id == project_id:
                return presentation.id

        for presentation in self._presentations.list_by_project(project_id):
            if presentation.title == "页面复活导出":
                return presentation.id

        created = self._presentations.create_presentation(
            Presentation(
                project_id=project_id,
                title="页面复活导出",
                description="页面复活工具导出的 PPTX 归档容器。",
            )
        )
        return created.id

    def _resolve_presentation(
        self,
        project_id: UUID,
        presentation_id: UUID | None,
    ) -> Presentation:
        if presentation_id is not None:
            presentation = self._presentations.get_presentation(presentation_id)
            if presentation is None:
                raise WorkflowError(f"汇报不存在：{presentation_id}")
            if presentation.project_id != project_id:
                raise WorkflowError("所选汇报不属于当前项目。")
            return presentation

        presentations = self._presentations.list_by_project(project_id)
        if presentations:
            return presentations[0]

        return self._presentations.create_presentation(
            Presentation(
                project_id=project_id,
                title="页面复活导入",
                description="由页面复活工具自动创建的汇报容器。",
            )
        )

    def _ensure_default_design_system(self) -> DesignSystem:
        design = default_presentation_design_system()
        existing = self._designs.get(design.id)
        if existing is None:
            return self._designs.save(design)
        return existing


def _layout_plan_from_recovery_scene(
    slide_id: UUID,
    scene: RenderScene,
    design_system_id: UUID,
) -> LayoutPlan:
    elements: list[LayoutElement] = []
    reading_order: list[str] = []
    for node in scene.sorted_nodes():
        if not isinstance(node, TextNode):
            continue
        role = (
            LayoutElementRole.TITLE
            if node.semantic_role in {"title", "subtitle"}
            else LayoutElementRole.BODY_TEXT
        )
        elements.append(
            LayoutElement(
                id=node.id,
                role=role,
                content_type=LayoutContentType.TEXT,
                text_content=node.text,
                x=node.x,
                y=node.y,
                width=node.width,
                height=node.height,
            )
        )
        reading_order.append(node.id)

    if not elements:
        elements.append(
            LayoutElement(
                id="recovery-body",
                role=LayoutElementRole.BODY_TEXT,
                content_type=LayoutContentType.TEXT,
                text_content="页面复活导入",
                x=0.7,
                y=0.5,
                width=8.0,
                height=0.7,
            )
        )
        reading_order = ["recovery-body"]

    hero = next(
        (element.id for element in elements if element.role == LayoutElementRole.TITLE),
        elements[0].id,
    )
    return LayoutPlan(
        slide_id=slide_id,
        layout_family=LayoutFamily.TEXTUAL_ARGUMENT,
        layout_variant=_RECOVERY_LAYOUT_VARIANT,
        page_width=scene.page_width,
        page_height=scene.page_height,
        hero_element_id=hero,
        reading_order=reading_order,
        elements=elements,
        design_system_id=design_system_id,
        visual_intent_id=uuid4(),
    )


def _safe_filename(value: str) -> str:
    cleaned = re.sub(r"[^\w\-.]+", "-", value.strip(), flags=re.UNICODE)
    cleaned = cleaned.strip("-") or "recovered-page"
    return cleaned[:120]


def _file_hash(path: Path) -> str:
    if not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()[:16]
