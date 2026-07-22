"""UI-facing facade for visual composition workflow."""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
from typing import Literal
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.visual.art_direction_service import ArtDirectionService
from archium.application.visual.layout_planning_service import LayoutPlanningService
from archium.application.visual.layout_validation_service import LayoutValidationService
from archium.application.visual.slide_preview_service import map_preview_pngs_by_order
from archium.application.visual.studio_scene_service import StudioSceneService
from archium.application.visual.visual_intent_presets import apply_visual_intent_preset
from archium.application.visual.visual_intent_service import VisualIntentService
from archium.application.visual.visual_workflow_service import (
    VisualWorkflowResult,
    VisualWorkflowService,
)
from archium.config.settings import Settings
from archium.domain.render import RenderResult
from archium.domain.slide import SlideSpec
from archium.domain.slide_semantic_qa import SlideSemanticFinding
from archium.domain.visual.art_direction import ArtDirection
from archium.domain.visual.design_system import DesignSystem
from archium.domain.visual.enums import LayoutFamily
from archium.domain.visual.layout import LayoutPlan
from archium.domain.visual.preferences import VisualPreferences
from archium.domain.visual.render_scene import RenderScene
from archium.domain.visual.validation import LayoutValidationReport
from archium.domain.visual.visual_intent import VisualIntent
from archium.exceptions import WorkflowError
from archium.infrastructure.database.repositories import PresentationRepository
from archium.infrastructure.database.visual_repositories import (
    ArtDirectionRepository,
    DesignSystemRepository,
    LayoutPlanRepository,
    VisualIntentRepository,
)
from archium.infrastructure.layout.layout_family_registry import get_layout_family_registry
from archium.infrastructure.llm.factory import create_llm_provider
from archium.infrastructure.renderers.pptx_renderer import PptxRenderer
from archium.infrastructure.renderers.pptxgen_renderer import PptxGenPresentationRenderer
from archium.ui.workflow_resources import get_workflow_checkpointer_manager
from archium.ui.workspace_service import _resolve_runtime_settings


@dataclass
class SlideVisualSnapshot:
    slide: SlideSpec
    visual_intent: VisualIntent | None
    layout_plan: LayoutPlan | None
    candidates: list[LayoutPlan] = field(default_factory=list)
    validation: LayoutValidationReport | None = None
    visual_critic: dict | None = None
    preview_image: str | None = None
    preview_kind: Literal["scene", "screenshot", "wireframe"] | None = None
    render_scene: RenderScene | None = None
    deferred_scene_repairs: list[SlideSemanticFinding] = field(default_factory=list)


@dataclass
class PresentationVisualSnapshot:
    presentation_id: UUID
    design_system: DesignSystem | None = None
    art_direction: ArtDirection | None = None
    slides: list[SlideVisualSnapshot] = field(default_factory=list)
    deck_qa_report: dict | None = None
    visual_critic_reports: list[dict] = field(default_factory=list)


def _create_visual_workflow_service(
    session: Session,
    *,
    settings: Settings,
    use_llm: bool,
) -> VisualWorkflowService:
    llm = create_llm_provider(settings) if use_llm and settings.llm_configured else None
    return VisualWorkflowService(
        session,
        llm=llm,
        settings=settings,
        checkpointer_manager=get_workflow_checkpointer_manager(settings),
    )


def run_visual_workflow(
    session: Session,
    project_id: UUID,
    presentation_id: UUID,
    *,
    preferences: VisualPreferences | None = None,
    require_art_direction_review: bool = True,
    use_llm: bool = False,
    export_pptx: bool = False,
    candidate_count: int = 3,
    settings: Settings | None = None,
) -> VisualWorkflowResult:
    resolved = _resolve_runtime_settings(settings)
    service = _create_visual_workflow_service(session, settings=resolved, use_llm=use_llm)
    try:
        return service.run(
            project_id,
            presentation_id,
            require_art_direction_review=require_art_direction_review,
            use_llm=use_llm and resolved.llm_configured,
            export_pptx=export_pptx,
            export_layout_instructions=True,
            candidate_count=candidate_count,
            preferences=preferences,
        )
    finally:
        # Shared checkpointer manager is owned by workflow_resources cache.
        pass


def continue_visual_after_art_direction_approval(
    session: Session,
    workflow_run_id: UUID,
    *,
    approve: bool = True,
    settings: Settings | None = None,
) -> VisualWorkflowResult:
    resolved = _resolve_runtime_settings(settings)
    service = _create_visual_workflow_service(session, settings=resolved, use_llm=False)
    return service.continue_after_art_direction_approval(
        workflow_run_id,
        approve=approve,
    )


def continue_visual_after_layout_review(
    session: Session,
    workflow_run_id: UUID,
    *,
    allow_invalid_layout_export: bool = False,
    settings: Settings | None = None,
) -> VisualWorkflowResult:
    resolved = _resolve_runtime_settings(settings)
    service = _create_visual_workflow_service(session, settings=resolved, use_llm=False)
    return service.continue_after_layout_review(
        workflow_run_id,
        allow_invalid_layout_export=allow_invalid_layout_export,
    )


def presentation_has_visual_layout(session: Session, presentation_id: UUID) -> bool:
    """Return True when every slide has a persisted LayoutPlan."""
    presentations = PresentationRepository(session)
    plans = LayoutPlanRepository(session)
    slides = presentations.list_slides(presentation_id)
    if not slides:
        return False
    for slide in slides:
        if slide.layout_plan_id is None:
            return False
        if plans.get(slide.layout_plan_id) is None:
            return False
    return True


def export_presentation_pptx_from_layout_plans(
    session: Session,
    presentation_id: UUID,
    *,
    settings: Settings | None = None,
) -> RenderResult:
    """Export editable PPTX from RenderScene compiled from saved LayoutPlans."""
    resolved = _resolve_runtime_settings(settings)
    presentations = PresentationRepository(session)
    presentation = presentations.get_presentation(presentation_id)
    if presentation is None:
        raise WorkflowError(f"Presentation {presentation_id} not found")
    if not presentation_has_visual_layout(session, presentation_id):
        raise WorkflowError("尚未生成视觉版式，无法按 LayoutPlan 导出 PPTX。")

    brief = None
    if presentation.current_brief_id is not None:
        brief = presentations.get_brief(presentation.current_brief_id)
    if brief is None:
        briefs = presentations.list_briefs(presentation_id)
        brief = briefs[0] if briefs else None
    if brief is None:
        raise WorkflowError("Brief is required before export")

    scene_service = StudioSceneService(session, settings=resolved)
    scene_results = scene_service.ensure_scenes_for_presentation(
        presentation_id,
        force_recompile=True,
    )
    if not scene_results:
        raise WorkflowError("无法为当前汇报编译 RenderScene，请先完成视觉编排。")

    slides = presentations.list_slides(presentation_id)
    slides_by_id = {slide.id: slide for slide in slides}
    ordered_scenes: list[tuple[RenderScene, str | None]] = []
    for result in scene_results:
        slide = slides_by_id.get(result.scene.slide_id)
        notes = slide.speaker_notes if slide is not None else None
        ordered_scenes.append((result.scene, notes or None))

    renderer = PptxRenderer(resolved)
    legacy = PptxGenPresentationRenderer(resolved, session=session)
    output_dir = legacy.output_dir(presentation_id, version=brief.version)
    pptx_path = output_dir / "presentation.pptx"
    rendered = renderer.export_presentation(
        title=brief.title,
        scenes=ordered_scenes,
        output_path=pptx_path,
    )
    return RenderResult(editable_pptx_path=rendered)


def generate_visual_and_export_pptx(
    session: Session,
    project_id: UUID,
    presentation_id: UUID,
    *,
    settings: Settings | None = None,
) -> VisualWorkflowResult:
    """Run visual composition with PPTX export enabled (streamlined export path)."""
    return run_visual_workflow(
        session,
        project_id,
        presentation_id,
        require_art_direction_review=False,
        use_llm=False,
        export_pptx=True,
        settings=settings,
    )


def get_presentation_visual_snapshot(
    session: Session,
    presentation_id: UUID,
    *,
    visual_critic_reports: list[dict] | None = None,
    deck_qa_report: dict | None = None,
    preview_paths: list[str] | None = None,
) -> PresentationVisualSnapshot:
    presentations = PresentationRepository(session)
    intents = VisualIntentRepository(session)
    plans = LayoutPlanRepository(session)
    art_repo = ArtDirectionRepository(session)
    design_repo = DesignSystemRepository(session)

    presentation = presentations.get_presentation(presentation_id)
    slides = presentations.list_slides(presentation_id)
    art_direction = None
    design_system = None

    if presentation is not None:
        for art in art_repo.list_by_project(presentation.project_id):
            if art.presentation_id == presentation_id:
                art_direction = art
                break
        if art_direction is None:
            arts = art_repo.list_by_project(presentation.project_id)
            art_direction = arts[0] if arts else None

    if art_direction is not None and art_direction.design_system_id is not None:
        design_system = design_repo.get(art_direction.design_system_id)

    critic_by_slide: dict[str, dict] = {}
    for report in visual_critic_reports or []:
        slide_key = str(report.get("slide_id") or "")
        if slide_key:
            critic_by_slide[slide_key] = report

    preview_by_index = map_preview_pngs_by_order(preview_paths or [])

    slide_snapshots: list[SlideVisualSnapshot] = []
    validator = LayoutValidationService()
    for index, slide in enumerate(slides):
        intent = (
            intents.get(slide.visual_intent_id)
            if slide.visual_intent_id is not None
            else intents.get_by_slide(slide.id)
        )
        plan = (
            plans.get(slide.layout_plan_id)
            if slide.layout_plan_id is not None
            else None
        )
        if plan is None:
            listed = plans.list_by_slide(slide.id)
            plan = listed[0] if listed else None
        candidates = plans.list_by_slide(slide.id)
        validation = None
        if plan is not None and design_system is not None:
            validation = validator.validate(
                plan,
                design_system,
                require_source=True,
                drawing_hero=plan.layout_family == LayoutFamily.DRAWING_FOCUS,
            )
        critic = critic_by_slide.get(str(slide.id))
        if critic is None and plan is not None:
            critic = critic_by_slide.get(str(plan.slide_id))
        slide_snapshots.append(
            SlideVisualSnapshot(
                slide=slide,
                visual_intent=intent,
                layout_plan=plan,
                candidates=candidates,
                validation=validation,
                visual_critic=critic,
                preview_image=preview_by_index.get(index),
            )
        )

    return PresentationVisualSnapshot(
        presentation_id=presentation_id,
        design_system=design_system,
        art_direction=art_direction,
        slides=slide_snapshots,
        deck_qa_report=deck_qa_report,
        visual_critic_reports=list(visual_critic_reports or []),
    )


def update_art_direction(
    session: Session,
    art_direction_id: UUID,
    updates: dict[str, object],
) -> ArtDirection:
    return ArtDirectionService(session).update(art_direction_id, updates)


def approve_art_direction(session: Session, art_direction_id: UUID) -> ArtDirection:
    return ArtDirectionService(session).approve(art_direction_id)


def regenerate_art_direction(
    session: Session,
    art_direction_id: UUID,
    feedback: str,
    *,
    use_llm: bool = False,
    settings: Settings | None = None,
) -> ArtDirection:
    resolved = _resolve_runtime_settings(settings)
    llm = create_llm_provider(resolved) if use_llm and resolved.llm_configured else None
    return ArtDirectionService(session, llm=llm).regenerate(art_direction_id, feedback)


def select_layout_candidate(
    session: Session,
    *,
    slide_id: UUID,
    layout_plan_id: UUID,
) -> LayoutPlan:
    from archium.application.visual.layout_locked import preserve_locked_elements
    from archium.application.visual.studio_scene_service import StudioSceneService
    from archium.application.visual.visual_history_service import VisualHistoryService
    from archium.domain.enums import RevisionSource

    presentations = PresentationRepository(session)
    plans = LayoutPlanRepository(session)
    intents = VisualIntentRepository(session)
    slide = presentations.get_slide(slide_id)
    plan = plans.get(layout_plan_id)
    if slide is None:
        raise ValueError(f"Slide {slide_id} not found")
    if plan is None:
        raise ValueError(f"LayoutPlan {layout_plan_id} not found")
    if plan.slide_id != slide_id:
        raise ValueError("LayoutPlan does not belong to this slide")
    template_backed = plan.source_template_id is not None
    if not template_backed and not get_layout_family_registry().get(plan.layout_family).implemented:
        raise WorkflowError(
            f"版式族「{plan.layout_family.value}」尚未实现 generator，暂不可选用。"
            "请在界面中选择已可用版式，或等待后续版本支持。"
        )
    previous_plan = None
    if slide.layout_plan_id is not None:
        previous_plan = plans.get(slide.layout_plan_id)
    merged = preserve_locked_elements(plan, previous_plan)
    if merged is not plan:
        merged = plans.save(merged)
        plan = merged
    slide.layout_plan_id = plan.id
    presentations.save_slide(slide)

    intent = (
        intents.get(slide.visual_intent_id)
        if slide.visual_intent_id is not None
        else intents.get_by_slide(slide.id)
    )
    VisualHistoryService(session).record_state(
        slide=slide,
        visual_intent=intent,
        layout_plan=plan,
        change_source=RevisionSource.MANUAL_EDIT,
        note=(
            "template layout switch"
            if template_backed
            else "layout candidate switch"
        ),
    )
    with contextlib.suppress(Exception):
        StudioSceneService(session).ensure_scene_for_slide(slide.id, force_recompile=True)
    return plan


def apply_template_to_slide(
    session: Session,
    *,
    slide_id: UUID,
    template_id: UUID,
    candidate_count: int = 3,
    settings: Settings | None = None,
) -> SlideVisualSnapshot:
    """Match a published template to the slide, fill content, and select the best plan."""
    from archium.application.visual.studio_scene_service import StudioSceneService
    from archium.application.visual.template_composition_service import TemplateCompositionService
    from archium.application.visual.visual_history_service import VisualHistoryService
    from archium.domain.enums import RevisionSource

    resolved = _resolve_runtime_settings(settings)
    composition = TemplateCompositionService(session, settings=resolved)
    result = composition.generate_candidates_for_slide(
        slide_id=slide_id,
        template_id=template_id,
        candidate_count=candidate_count,
        select_best=True,
    )
    presentations = PresentationRepository(session)
    intents = VisualIntentRepository(session)
    slide = presentations.get_slide(slide_id)
    if slide is None:
        raise WorkflowError(f"页面不存在：{slide_id}")
    intent = (
        intents.get(slide.visual_intent_id)
        if slide.visual_intent_id is not None
        else intents.get_by_slide(slide.id)
    )
    VisualHistoryService(session).record_state(
        slide=slide,
        visual_intent=intent,
        layout_plan=result.selected_plan,
        change_source=RevisionSource.MANUAL_EDIT,
        note=f"apply template {result.template.name}",
    )
    with contextlib.suppress(Exception):
        StudioSceneService(session, settings=resolved).ensure_scene_for_slide(
            slide.id,
            force_recompile=True,
        )

    snapshot = get_presentation_visual_snapshot(session, slide.presentation_id)
    for index, item in enumerate(snapshot.slides):
        if item.slide.id == slide_id:
            snapshot.slides[index] = SlideVisualSnapshot(
                slide=item.slide,
                visual_intent=item.visual_intent,
                layout_plan=result.selected_plan or item.layout_plan,
                candidates=result.layout_plans or item.candidates,
                validation=item.validation,
                visual_critic=item.visual_critic,
                preview_image=item.preview_image,
                preview_kind=item.preview_kind,
                render_scene=item.render_scene,
            )
            return snapshot.slides[index]
    raise WorkflowError(f"页面快照缺失：{slide_id}")


def replan_slide(
    session: Session,
    *,
    slide_id: UUID,
    preset: str | None = None,
    candidate_count: int = 3,
    use_llm: bool = False,
    settings: Settings | None = None,
) -> SlideVisualSnapshot:
    """Re-plan a single slide; optional preset tweaks VisualIntent before planning."""
    resolved = _resolve_runtime_settings(settings)
    presentations = PresentationRepository(session)
    intents = VisualIntentRepository(session)
    plans = LayoutPlanRepository(session)
    design_repo = DesignSystemRepository(session)

    slide = presentations.get_slide(slide_id)
    if slide is None:
        raise ValueError(f"Slide {slide_id} not found")

    intent = (
        intents.get(slide.visual_intent_id)
        if slide.visual_intent_id is not None
        else intents.get_by_slide(slide.id)
    )
    if intent is None:
        llm = create_llm_provider(resolved) if use_llm and resolved.llm_configured else None
        intent = VisualIntentService(session, llm=llm).generate_for_slide(
            slide, use_llm=use_llm and resolved.llm_configured
        )
        slide.visual_intent_id = intent.id
        presentations.save_slide(slide)

    intent = apply_visual_intent_preset(intent, preset)
    intent = intents.save(intent)

    presentation = presentations.get_presentation(slide.presentation_id)
    art = None
    design = None
    art_id = intent.art_direction_id
    if art_id is not None:
        art = ArtDirectionRepository(session).get(art_id)
        if art is not None and art.design_system_id is not None:
            design = design_repo.get(art.design_system_id)
    if design is None and presentation is not None:
        arts = ArtDirectionRepository(session).list_by_project(presentation.project_id)
        for item in arts:
            if item.presentation_id == slide.presentation_id and item.design_system_id:
                design = design_repo.get(item.design_system_id)
                art = item
                break
        if design is None and arts and arts[0].design_system_id:
            design = design_repo.get(arts[0].design_system_id)
            art = arts[0]
    if design is None:
        from archium.domain.visual.defaults import default_presentation_design_system

        design = design_repo.save(default_presentation_design_system())

    llm = create_llm_provider(resolved) if use_llm and resolved.llm_configured else None
    planner = LayoutPlanningService(session, llm=llm)
    previous_plan = None
    if slide.layout_plan_id is not None:
        previous_plan = plans.get(slide.layout_plan_id)
    if previous_plan is None:
        listed = plans.list_by_slide(slide.id)
        previous_plan = listed[0] if listed else None
    project_id = presentation.project_id if presentation is not None else None
    candidates = planner.generate_candidates(
        slide=slide,
        visual_intent_id=intent.id,
        art_direction_id=art.id if art else None,
        design_system_id=design.id,
        candidate_count=candidate_count,
        project_id=project_id,
        previous_layout_plan=previous_plan,
    )
    saved_candidates: list[LayoutPlan] = []
    for plan, _report in candidates:
        saved_candidates.append(plans.save(plan))
    best = planner.select_best(
        candidates,
        previous_layout_plan=previous_plan,
        style_preference=planner.last_style_preference,
    )
    best = plans.save(best)
    slide.layout_plan_id = best.id
    presentations.save_slide(slide)

    validation = LayoutValidationService().validate(
        best,
        design,
        require_source=True,
        drawing_hero=best.layout_family == LayoutFamily.DRAWING_FOCUS,
    )
    return SlideVisualSnapshot(
        slide=slide,
        visual_intent=intent,
        layout_plan=best,
        candidates=saved_candidates or plans.list_by_slide(slide.id),
        validation=validation,
    )

