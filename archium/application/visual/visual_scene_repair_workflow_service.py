"""Compile RenderScenes from visual workflow artifacts and run scene repair."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.artifact_policy_service import save_render_scene
from archium.application.visual.asset_reference import (
    build_asset_reference_context,
    content_refs_from_plan,
)
from archium.application.visual.render_scene_compiler import RenderSceneCompiler
from archium.application.visual.scene_compilers.base import SceneCompileContext
from archium.application.visual.scene_compilers.chain import (
    SceneCompilerChain,
    default_scene_compilers,
)
from archium.application.visual.scene_repair_service import SceneRepairService
from archium.config.settings import Settings, get_settings
from archium.domain.export_authority import FORMAL_DELIVERY_PPTX_FILENAME
from archium.domain.slide import SlideSpec
from archium.domain.visual.art_direction import ArtDirection
from archium.domain.visual.design_system import DesignSystem
from archium.domain.visual.layout import LayoutPlan
from archium.domain.visual.render_scene import RenderScene
from archium.infrastructure.database.repositories import (
    PresentationRepository,
    ProjectRepository,
)
from archium.infrastructure.database.visual_repositories import (
    ArtDirectionRepository,
    RenderSceneRepository,
    VisualIntentRepository,
)
from archium.infrastructure.renderers.pptxgen.layout_plan_adapter import SlideContentBundle


@dataclass(frozen=True)
class VisualSceneRepairWorkflowResult:
    scenes: list[RenderScene]
    scene_paths: list[str]
    repair_actions: int
    repair_rounds: int
    remaining_issue_count: int
    scene_pptx_path: str | None = None
    warnings: list[str] = field(default_factory=list)


class VisualSceneRepairWorkflowService:
    """Bridge LayoutPlan exports → RenderScene QA/repair loop for visual workflow."""

    def __init__(
        self,
        session: Session,
        *,
        settings: Settings | None = None,
        compiler: RenderSceneCompiler | None = None,
        compiler_chain: SceneCompilerChain | None = None,
        scene_repair: SceneRepairService | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        inner = compiler or RenderSceneCompiler()
        self._compiler = inner
        self._compiler_chain = compiler_chain or SceneCompilerChain(
            compilers=default_scene_compilers(inner=inner)
        )
        self._scene_repair = scene_repair or SceneRepairService()
        self._presentations = PresentationRepository(session)
        self._projects = ProjectRepository(session)
        self._art_directions = ArtDirectionRepository(session)
        self._intents = VisualIntentRepository(session)
        self._scenes = RenderSceneRepository(session)
        self._last_compile_warnings: list[str] = []

    def compile_scenes(
        self,
        *,
        slides: list[SlideSpec],
        plans: list[LayoutPlan],
        design_system: DesignSystem,
        presentation_id: UUID,
        project_id: UUID,
        art_direction: ArtDirection | None = None,
        reference_style: ReferenceStyleProfile | None = None,
    ) -> list[RenderScene]:
        self._last_compile_warnings = []
        if art_direction is None:
            art_direction = self._resolve_art_direction(project_id, presentation_id)
        if reference_style is None:
            reference_style = self._resolve_reference_style(project_id)
        slide_by_id = {slide.id: slide for slide in slides}
        compiled: list[RenderScene] = []
        for plan in plans:
            slide = slide_by_id.get(plan.slide_id)
            if slide is None:
                self._last_compile_warnings.append(
                    f"SCENE_COMPILE_SKIPPED:missing_slide:{plan.slide_id}"
                )
                continue
            intent = None
            if slide.visual_intent_id is not None:
                intent = self._intents.get(slide.visual_intent_id)
            if intent is None:
                intent = self._intents.get_by_slide(slide.id)
            bundle = self._build_content_bundle(project_id=project_id, slide=slide, plan=plan)
            result = self._compiler_chain.compile(
                SceneCompileContext(
                    slide=slide,
                    layout_plan=plan,
                    design_system=design_system,
                    content_bundle=bundle,
                    visual_intent=intent,
                    art_direction=art_direction,
                    reference_style=reference_style,
                    presentation_id=presentation_id,
                )
            )
            scene = result.scene
            from archium.application.visual.image_derivative_service import (
                ImageDerivativeService,
            )

            applied = ImageDerivativeService(
                self._session,
                settings=self._settings,
            ).apply_to_scene(
                scene,
                project_id=project_id,
                design_system=design_system,
            )
            compiled.append(applied.scene)
        return compiled

    def _resolve_art_direction(
        self,
        project_id: UUID,
        presentation_id: UUID,
    ) -> ArtDirection | None:
        matched: ArtDirection | None = None
        for art in self._art_directions.list_by_project(project_id):
            if art.presentation_id == presentation_id:
                matched = art
                break
        if matched is None:
            arts = self._art_directions.list_by_project(project_id)
            matched = arts[0] if arts else None
        return matched

    def _resolve_reference_style(self, project_id: UUID) -> ReferenceStyleProfile | None:
        profiles = self._projects.list_reference_style_profiles(project_id)
        if not profiles:
            return None
        approved = [profile for profile in profiles if profile.is_approved]
        return (approved or profiles)[0]

    def repair_and_persist(
        self,
        *,
        presentation_id: UUID,
        project_id: UUID,
        slides: list[SlideSpec],
        plans: list[LayoutPlan],
        design_system: DesignSystem,
        output_dir: Path,
        max_rounds: int = 2,
        export_scene_pptx: bool = False,
        deck_title: str = "Archium Visual Composition",
    ) -> VisualSceneRepairWorkflowResult:
        scenes = self.compile_scenes(
            slides=slides,
            plans=plans,
            design_system=design_system,
            presentation_id=presentation_id,
            project_id=project_id,
        )
        warnings = list(self._last_compile_warnings)
        if not scenes:
            if plans and not warnings:
                warnings.append(
                    "SCENE_COMPILE_EMPTY: no scenes produced from layout plans"
                )
            return VisualSceneRepairWorkflowResult(
                scenes=[],
                scene_paths=[],
                repair_actions=0,
                repair_rounds=0,
                remaining_issue_count=0,
                warnings=warnings,
            )

        slide_orders = {slide.id: slide.order for slide in slides}
        batch = self._scene_repair.repair_deck(
            presentation_id,
            scenes,
            max_rounds=max_rounds,
            slide_orders=slide_orders,
        )

        scene_root = output_dir / "render_scenes"
        scene_root.mkdir(parents=True, exist_ok=True)
        scene_paths: list[str] = []
        slide_by_id = {slide.id: slide for slide in slides}
        persisted: list[RenderScene] = []
        for scene in batch.scenes:
            slide = slide_by_id.get(scene.slide_id)
            order = slide.order if slide is not None else 0
            rel_dir = scene_root / f"slide_{order + 1:02d}"
            rel_dir.mkdir(parents=True, exist_ok=True)
            existing = self._scenes.get_by_layout_plan(scene.layout_plan_id)
            if existing is not None:
                scene = scene.model_copy(
                    update={
                        "id": existing.id,
                        "version": existing.version + 1,
                        "created_at": existing.created_at,
                    }
                )
            scene_path = rel_dir / "render_scene.json"
            scene_path.write_text(
                json.dumps(scene.model_dump(mode="json"), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            scene_paths.append(str(scene_path))
            saved = save_render_scene(self._scenes, scene)
            # DOM-011: repair mutates scene geometry — keep LayoutPlan mirror in sync.
            if slide is not None and slide.layout_plan_id is not None:
                from archium.application.visual.studio_scene_edit_service import (
                    sync_layout_geometry_from_scene,
                )
                from archium.infrastructure.database.visual_repositories import (
                    LayoutPlanRepository,
                )

                plans = LayoutPlanRepository(self._session)
                plan = plans.get(slide.layout_plan_id)
                if plan is not None:
                    plans.save(sync_layout_geometry_from_scene(saved, plan))
            persisted.append(saved)

        scene_pptx_path: str | None = None
        if export_scene_pptx and persisted:
            scene_by_slide = {scene.slide_id: scene for scene in persisted}
            ordered_slides = sorted(slides, key=lambda item: item.order)
            pairs = [
                (scene_by_slide[slide.id], slide.speaker_notes or None)
                for slide in ordered_slides
                if slide.id in scene_by_slide
            ]
            if len(pairs) == 1:
                from archium.infrastructure.renderers.pptx_renderer import (
                    maybe_export_scene_pptx,
                    scene_pptx_unavailable_reason,
                )

                exported = maybe_export_scene_pptx(
                    pairs[0][0],
                    output_dir / FORMAL_DELIVERY_PPTX_FILENAME,
                    title=deck_title,
                    speaker_notes=pairs[0][1],
                    settings=self._settings,
                    project_id=project_id,
                )
                if exported is not None:
                    scene_pptx_path = str(exported)
                else:
                    reason = scene_pptx_unavailable_reason(self._settings) or "unknown"
                    warnings.append(f"Scene PPTX export skipped: {reason}")
            elif pairs:
                from archium.infrastructure.renderers.pptx_renderer import (
                    PptxRenderer,
                    scene_pptx_unavailable_reason,
                )

                skip_reason = scene_pptx_unavailable_reason(self._settings)
                if skip_reason is not None:
                    warnings.append(f"Scene PPTX export skipped: {skip_reason}")
                else:
                    renderer = PptxRenderer(self._settings)
                    exported = renderer.export_presentation(
                        title=deck_title,
                        scenes=pairs,
                        output_path=output_dir / FORMAL_DELIVERY_PPTX_FILENAME,
                        project_id=project_id,
                    )
                    scene_pptx_path = str(exported)
        elif export_scene_pptx and not persisted:
            warnings.append("Scene PPTX export skipped: no persisted scenes")

        return VisualSceneRepairWorkflowResult(
            scenes=persisted,
            scene_paths=scene_paths,
            repair_actions=len(batch.actions),
            repair_rounds=batch.rounds,
            remaining_issue_count=batch.remaining_issue_count,
            scene_pptx_path=scene_pptx_path,
            warnings=warnings,
        )

    def _build_content_bundle(
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
