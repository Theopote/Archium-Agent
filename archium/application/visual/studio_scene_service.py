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
from archium.config.settings import Settings, get_settings
from archium.domain.slide import SlideSpec
from archium.domain.visual.design_system import DesignSystem
from archium.domain.visual.defaults import default_presentation_design_system
from archium.domain.visual.layout import LayoutPlan
from archium.domain.visual.render_scene import RenderScene, compute_scene_hash
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


class StudioSceneService:
    """Keep Studio visual previews and persistence on RenderScene."""

    def __init__(
        self,
        session: Session,
        *,
        settings: Settings | None = None,
        compiler: RenderSceneCompiler | None = None,
        canvas_renderer: CanvasRenderer | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._compiler = compiler or RenderSceneCompiler()
        self._canvas = canvas_renderer or CanvasRenderer()
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
        return self._compiler.compile(
            slide=slide,
            layout_plan=plan,
            design_system=design_system,
            content_bundle=bundle,
            visual_intent=visual_intent,
            presentation_id=presentation_id or slide.presentation_id,
        )

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
                preview = self._ensure_preview(slide.presentation_id, existing)
                return StudioSceneResult(
                    scene=existing,
                    scene_hash=compute_scene_hash(existing),
                    preview_path=preview,
                    reused=True,
                )

        if existing is not None:
            scene = scene.model_copy(
                update={
                    "id": existing.id,
                    "version": existing.version + 1,
                    "created_at": existing.created_at,
                }
            )
        saved = self._scenes.save(scene)
        self.invalidate_preview_cache(
            slide.presentation_id,
            layout_plan_id=plan.id,
        )
        preview = self._ensure_preview(slide.presentation_id, saved)
        return StudioSceneResult(
            scene=saved,
            scene_hash=compute_scene_hash(saved),
            preview_path=preview,
            reused=False,
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

    def _ensure_preview(self, presentation_id: UUID, scene: RenderScene) -> Path:
        path = self.preview_cache_path(presentation_id, scene)
        if path.is_file():
            return path
        return self._canvas.render_preview(scene, path)

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
