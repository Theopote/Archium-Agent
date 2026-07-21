"""Compile, persist, and preview RenderScene for Presentation Studio."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.visual.asset_reference import (
    build_asset_reference_context,
    content_refs_from_plan,
)
from archium.application.visual.render_scene_compiler import RenderSceneCompiler
from archium.application.visual.scene_compilers import (
    SceneCompileContext,
    SceneCompilerChain,
)
from archium.application.visual.scene_history_service import SceneHistoryService
from archium.application.visual.scene_repair_service import SceneRepairService
from archium.config.settings import Settings, get_settings
from archium.domain.enums import RevisionSource
from archium.domain.slide import SlideSpec
from archium.domain.slide_semantic_qa import SlideSemanticFinding
from archium.domain.visual.architectural_content_schema import ArchitecturalContentSchema
from archium.domain.visual.defaults import default_presentation_design_system
from archium.domain.visual.design_system import DesignSystem
from archium.domain.visual.layout import LayoutPlan
from archium.domain.visual.render_scene import RenderScene, compute_scene_hash
from archium.domain.visual.scene_repair import SceneRepairAction, SceneRepairBatchResult
from archium.domain.visual.visual_intent import VisualIntent
from archium.infrastructure.database.repositories import PresentationRepository
from archium.infrastructure.database.visual_repositories import (
    ArtDirectionRepository,
    DesignSystemRepository,
    LayoutPlanRepository,
    RenderSceneRepository,
    VisualIntentRepository,
)
from archium.infrastructure.renderers.canvas_renderer import CanvasRenderer
from archium.infrastructure.renderers.pptxgen.layout_plan_adapter import SlideContentBundle


@dataclass(frozen=True)
class StudioSceneResult:
    scene: RenderScene
    scene_hash: str
    preview_path: Path
    reused: bool
    safe_repair_actions: tuple[SceneRepairAction, ...] = ()
    deferred_repair_findings: tuple[SlideSemanticFinding, ...] = ()


class StudioSceneService:
    """Keep Studio visual previews and persistence on RenderScene."""

    def __init__(
        self,
        session: Session,
        *,
        settings: Settings | None = None,
        compiler: RenderSceneCompiler | None = None,
        compiler_chain: SceneCompilerChain | None = None,
        canvas_renderer: CanvasRenderer | None = None,
        scene_repair: SceneRepairService | None = None,
    ) -> None:
        from archium.application.visual.scene_compilers.chain import default_scene_compilers

        self._session = session
        self._settings = settings or get_settings()
        inner = compiler or RenderSceneCompiler()
        self._compiler = inner
        self._compiler_chain = compiler_chain or SceneCompilerChain(
            compilers=default_scene_compilers(inner=inner)
        )
        self._canvas = canvas_renderer or CanvasRenderer()
        self._scene_repair = scene_repair or SceneRepairService()
        self._scenes = RenderSceneRepository(session)
        self._presentations = PresentationRepository(session)
        self._plans = LayoutPlanRepository(session)
        self._intents = VisualIntentRepository(session)
        self._design_repo = DesignSystemRepository(session)
        self._art_repo = ArtDirectionRepository(session)

    def preview_cache_path(self, presentation_id: UUID, scene: RenderScene) -> Path:
        cache_dir = (
            self._settings.output_path
            / "studio-scene-previews"
            / str(presentation_id)
        )
        cache_dir.mkdir(parents=True, exist_ok=True)
        digest = compute_scene_hash(scene)[:16]
        return cache_dir / f"{scene.layout_plan_id}_{digest}.png"

    def render_scene_preview(self, presentation_id: UUID, scene: RenderScene) -> Path:
        """Render or reuse a PNG preview for an arbitrary RenderScene."""
        return self._ensure_preview(presentation_id, scene)

    def invalidate_preview_cache(
        self,
        presentation_id: UUID,
        *,
        layout_plan_id: UUID | None = None,
    ) -> None:
        cache_dir = (
            self._settings.output_path
            / "studio-scene-previews"
            / str(presentation_id)
        )
        if not cache_dir.is_dir():
            return
        for path in cache_dir.glob("*.png"):
            if layout_plan_id is None or path.name.startswith(f"{layout_plan_id}_"):
                path.unlink(missing_ok=True)

    def build_content_bundle(
        self,
        *,
        project_id: UUID,
        slide: SlideSpec,
        plan: LayoutPlan,
    ) -> SlideContentBundle:
        context = build_asset_reference_context(
            self._session,
            project_id=project_id,
            content_refs=content_refs_from_plan(plan),
            settings=self._settings,
        )
        return SlideContentBundle(
            asset_paths=dict(context.resolved_paths),
            asset_origins=dict(context.asset_origins),
            page_number=slide.order + 1,
            speaker_notes=slide.speaker_notes or None,
        )

    def compile_scene(
        self,
        *,
        slide: SlideSpec,
        plan: LayoutPlan,
        design_system: DesignSystem,
        visual_intent: VisualIntent | None = None,
        content_schema: ArchitecturalContentSchema | None = None,
        presentation_id: UUID | None = None,
        project_id: UUID | None = None,
    ) -> RenderScene:
        resolved_project = project_id
        if resolved_project is None:
            presentation = self._presentations.get_presentation(
                presentation_id or slide.presentation_id
            )
            if presentation is not None:
                resolved_project = presentation.project_id
        bundle = SlideContentBundle()
        if resolved_project is not None:
            bundle = self.build_content_bundle(
                project_id=resolved_project,
                slide=slide,
                plan=plan,
            )
        result = self._compiler_chain.compile(
            SceneCompileContext(
                slide=slide,
                layout_plan=plan,
                design_system=design_system,
                content_bundle=bundle,
                visual_intent=visual_intent,
                content_schema=content_schema,
                presentation_id=presentation_id or slide.presentation_id,
            )
        )
        return result.scene

    def ensure_scene_for_slide(
        self,
        slide_id: UUID,
        *,
        force_recompile: bool = False,
    ) -> StudioSceneResult | None:
        slide = self._presentations.get_slide(slide_id)
        if slide is None or slide.layout_plan_id is None:
            return None
        plan = self._plans.get(slide.layout_plan_id)
        if plan is None:
            return None
        presentation = self._presentations.get_presentation(slide.presentation_id)
        if presentation is None:
            return None

        design = self._resolve_design_system(presentation.project_id, slide.presentation_id)
        intent = None
        if slide.visual_intent_id is not None:
            intent = self._intents.get(slide.visual_intent_id)

        existing = self._scenes.get_by_layout_plan(plan.id)
        scene = self.compile_scene(
            slide=slide,
            plan=plan,
            design_system=design,
            visual_intent=intent,
            presentation_id=slide.presentation_id,
            project_id=presentation.project_id,
        )
        if existing is not None and not force_recompile:
            comparable = scene.model_copy(
                update={
                    "id": existing.id,
                    "version": existing.version,
                    "created_at": existing.created_at,
                    "updated_at": existing.updated_at,
                }
            )
            if compute_scene_hash(comparable) == compute_scene_hash(existing):
                prepared, batch = self._run_scene_repair(existing, slide)
                saved = existing
                if compute_scene_hash(prepared) != compute_scene_hash(existing):
                    saved = self._scenes.save(
                        prepared.model_copy(
                            update={
                                "id": existing.id,
                                "version": existing.version + 1,
                                "created_at": existing.created_at,
                            }
                        )
                    )
                    self._record_safe_auto_repair(slide, saved, batch)
                    self.invalidate_preview_cache(
                        slide.presentation_id,
                        layout_plan_id=plan.id,
                    )
                preview = self._ensure_preview(slide.presentation_id, saved)
                return self._build_scene_result(
                    scene=saved,
                    preview_path=preview,
                    reused=True,
                    batch=batch,
                )

        if existing is not None:
            scene = scene.model_copy(
                update={
                    "id": existing.id,
                    "version": existing.version + 1,
                    "created_at": existing.created_at,
                }
            )
        prepared, batch = self._run_scene_repair(scene, slide)
        saved = self._scenes.save(prepared)
        self._record_safe_auto_repair(slide, saved, batch)
        self.invalidate_preview_cache(
            slide.presentation_id,
            layout_plan_id=plan.id,
        )
        preview = self._ensure_preview(slide.presentation_id, saved)
        return self._build_scene_result(
            scene=saved,
            preview_path=preview,
            reused=False,
            batch=batch,
        )

    def refresh_after_layout_edit(
        self,
        *,
        presentation_id: UUID,
        plan: LayoutPlan,
        slide_id: UUID | None = None,
    ) -> StudioSceneResult | None:
        """Invalidate caches and recompile scene after LayoutPlan mutation."""
        wireframe = (
            self._settings.output_path
            / "studio-previews"
            / str(presentation_id)
            / f"{plan.id}.png"
        )
        if wireframe.is_file():
            wireframe.unlink(missing_ok=True)
        self.invalidate_preview_cache(presentation_id, layout_plan_id=plan.id)
        target_slide_id = slide_id or plan.slide_id
        return self.ensure_scene_for_slide(target_slide_id, force_recompile=True)

    def ensure_scenes_for_presentation(
        self,
        presentation_id: UUID,
        *,
        force_recompile: bool = False,
    ) -> list[StudioSceneResult]:
        results: list[StudioSceneResult] = []
        for slide in self._presentations.list_slides(presentation_id):
            result = self.ensure_scene_for_slide(
                slide.id,
                force_recompile=force_recompile,
            )
            if result is not None:
                results.append(result)
        return results

    def _run_scene_repair(
        self,
        scene: RenderScene,
        slide: SlideSpec,
    ) -> tuple[RenderScene, SceneRepairBatchResult | None]:
        if not bool(getattr(self._settings, "scene_repair_enabled", True)):
            return scene, None
        max_rounds = int(getattr(self._settings, "scene_repair_max_rounds", 2))
        batch = self._scene_repair.repair_deck(
            slide.presentation_id,
            [scene],
            max_rounds=max_rounds,
            slide_orders={scene.slide_id: slide.order},
        )
        repaired = batch.scenes[0] if batch.scenes else scene
        return repaired, batch

    def _build_scene_result(
        self,
        *,
        scene: RenderScene,
        preview_path: Path,
        reused: bool,
        batch: SceneRepairBatchResult | None,
    ) -> StudioSceneResult:
        safe_actions: tuple[SceneRepairAction, ...] = ()
        deferred: tuple[SlideSemanticFinding, ...] = ()
        if batch is not None:
            safe_actions = tuple(batch.actions)
            deferred = tuple(batch.deferred_findings)
        return StudioSceneResult(
            scene=scene,
            scene_hash=compute_scene_hash(scene),
            preview_path=preview_path,
            reused=reused,
            safe_repair_actions=safe_actions,
            deferred_repair_findings=deferred,
        )

    def _record_safe_auto_repair(
        self,
        slide: SlideSpec,
        scene: RenderScene,
        batch: SceneRepairBatchResult | None,
    ) -> None:
        if batch is None or not batch.actions:
            return
        summary = "; ".join(
            f"{action.action_type}@{action.node_id}" for action in batch.actions
        )
        SceneHistoryService(self._session).record_scene(
            slide=slide,
            scene=scene,
            change_source=RevisionSource.AUTO_REPAIR,
            scene_revision_source="automatic_repair",
            note=summary or "safe auto repair",
        )

    def _ensure_preview(self, presentation_id: UUID, scene: RenderScene) -> Path:
        path = self.preview_cache_path(presentation_id, scene)
        if path.is_file():
            return path
        from archium.application.visual.asset_path_resolver import (
            AssetPathResolveContext,
            AssetPathResolver,
        )

        presentation = self._presentations.get_presentation(presentation_id)
        project_id = presentation.project_id if presentation is not None else None
        render_scene = AssetPathResolver().resolve_scene(
            scene,
            AssetPathResolveContext(
                project_id=project_id,
                project_storage_root=self._settings.project_storage_path,
            ),
        )
        return self._canvas.render_preview(render_scene, path)

    def _resolve_design_system(
        self,
        project_id: UUID,
        presentation_id: UUID,
    ) -> DesignSystem:
        art_direction = None
        for art in self._art_repo.list_by_project(project_id):
            if art.presentation_id == presentation_id:
                art_direction = art
                break
        if art_direction is None:
            arts = self._art_repo.list_by_project(project_id)
            art_direction = arts[0] if arts else None
        if art_direction is not None and art_direction.design_system_id is not None:
            design = self._design_repo.get(art_direction.design_system_id)
            if design is not None:
                return design
        return default_presentation_design_system()
