"""Compile RenderScenes from visual workflow artifacts and run scene repair."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.visual.asset_reference import (
    build_asset_reference_context,
    content_refs_from_plan,
)
from archium.application.visual.render_scene_compiler import RenderSceneCompiler
from archium.application.visual.scene_repair_service import SceneRepairService
from archium.config.settings import Settings, get_settings
from archium.domain.slide import SlideSpec
from archium.domain.visual.design_system import DesignSystem
from archium.domain.visual.layout import LayoutPlan
from archium.domain.visual.render_scene import RenderScene
from archium.infrastructure.database.repositories import PresentationRepository
from archium.infrastructure.database.visual_repositories import (
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


class VisualSceneRepairWorkflowService:
    """Bridge LayoutPlan exports → RenderScene QA/repair loop for visual workflow."""

    def __init__(
        self,
        session: Session,
        *,
        settings: Settings | None = None,
        compiler: RenderSceneCompiler | None = None,
        scene_repair: SceneRepairService | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._compiler = compiler or RenderSceneCompiler()
        self._scene_repair = scene_repair or SceneRepairService()
        self._presentations = PresentationRepository(session)
        self._intents = VisualIntentRepository(session)
        self._scenes = RenderSceneRepository(session)

    def compile_scenes(
        self,
        *,
        slides: list[SlideSpec],
        plans: list[LayoutPlan],
        design_system: DesignSystem,
        presentation_id: UUID,
        project_id: UUID,
    ) -> list[RenderScene]:
        slide_by_id = {slide.id: slide for slide in slides}
        compiled: list[RenderScene] = []
        for plan in plans:
            slide = slide_by_id.get(plan.slide_id)
            if slide is None:
                continue
            intent = None
            if slide.visual_intent_id is not None:
                intent = self._intents.get(slide.visual_intent_id)
            if intent is None:
                intent = self._intents.get_by_slide(slide.id)
            bundle = self._build_content_bundle(project_id=project_id, slide=slide, plan=plan)
            compiled.append(
                self._compiler.compile(
                    slide=slide,
                    layout_plan=plan,
                    design_system=design_system,
                    content_bundle=bundle,
                    visual_intent=intent,
                    presentation_id=presentation_id,
                )
            )
        return compiled

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
        if not scenes:
            return VisualSceneRepairWorkflowResult(
                scenes=[],
                scene_paths=[],
                repair_actions=0,
                repair_rounds=0,
                remaining_issue_count=0,
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
        for scene in batch.scenes:
            slide = slide_by_id.get(scene.slide_id)
            order = slide.order if slide is not None else 0
            rel_dir = scene_root / f"slide_{order + 1:02d}"
            rel_dir.mkdir(parents=True, exist_ok=True)
            scene_path = rel_dir / "render_scene.json"
            scene_path.write_text(
                json.dumps(scene.model_dump(mode="json"), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            scene_paths.append(str(scene_path))
            self._scenes.save(scene)

        scene_pptx_path: str | None = None
        if export_scene_pptx and batch.scenes:
            scene_by_slide = {scene.slide_id: scene for scene in batch.scenes}
            ordered_slides = sorted(slides, key=lambda item: item.order)
            pairs = [
                (scene_by_slide[slide.id], slide.speaker_notes or None)
                for slide in ordered_slides
                if slide.id in scene_by_slide
            ]
            if len(pairs) == 1:
                from archium.infrastructure.renderers.pptx_renderer import maybe_export_scene_pptx

                exported = maybe_export_scene_pptx(
                    pairs[0][0],
                    output_dir / "presentation_from_scenes.pptx",
                    title=deck_title,
                    speaker_notes=pairs[0][1],
                    settings=self._settings,
                )
                if exported is not None:
                    scene_pptx_path = str(exported)
            elif pairs:
                from archium.infrastructure.renderers.pptx_renderer import PptxRenderer

                renderer = PptxRenderer(self._settings)
                if renderer._cli.is_available():
                    exported = renderer.export_presentation(
                        title=deck_title,
                        scenes=pairs,
                        output_path=output_dir / "presentation_from_scenes.pptx",
                    )
                    scene_pptx_path = str(exported)

        return VisualSceneRepairWorkflowResult(
            scenes=batch.scenes,
            scene_paths=scene_paths,
            repair_actions=len(batch.actions),
            repair_rounds=batch.rounds,
            remaining_issue_count=batch.remaining_issue_count,
            scene_pptx_path=scene_pptx_path,
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
