"""UI-facing facade for visual composition workflow."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.visual.art_direction_service import ArtDirectionService
from archium.application.visual.layout_planning_service import LayoutPlanningService
from archium.application.visual.layout_validation_service import LayoutValidationService
from archium.application.visual.visual_intent_service import VisualIntentService
from archium.application.visual.visual_workflow_service import (
    VisualWorkflowResult,
    VisualWorkflowService,
)
from archium.config.settings import Settings
from archium.domain.enums import ApprovalStatus
from archium.domain.slide import SlideSpec
from archium.domain.visual.art_direction import ArtDirection
from archium.domain.visual.design_system import DesignSystem
from archium.domain.visual.enums import DensityLevel, LayoutFamily, VisualContentType
from archium.domain.visual.layout import LayoutPlan
from archium.domain.visual.preferences import VisualPreferences
from archium.domain.visual.validation import LayoutValidationReport
from archium.domain.render import RenderResult
from archium.domain.visual.visual_intent import VisualIntent
from archium.exceptions import WorkflowError
from archium.infrastructure.database.repositories import PresentationRepository
from archium.infrastructure.layout.layout_family_registry import get_layout_family_registry
from archium.infrastructure.renderers.pptxgen_renderer import PptxGenPresentationRenderer
from archium.infrastructure.database.visual_repositories import (
    ArtDirectionRepository,
    DesignSystemRepository,
    LayoutPlanRepository,
    VisualIntentRepository,
)
from archium.infrastructure.llm.factory import create_llm_provider
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
    """Export editable PPTX from saved LayoutPlans (no template re-layout)."""
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

    slides = presentations.list_slides(presentation_id)
    snapshot = get_presentation_visual_snapshot(session, presentation_id)
    design = snapshot.design_system
    if design is None:
        from archium.domain.visual.defaults import default_presentation_design_system

        design = default_presentation_design_system()

    layout_plans: list[LayoutPlan] = []
    for item in snapshot.slides:
        if item.layout_plan is None:
            raise WorkflowError(
                f"第 {item.slide.order + 1} 页缺少 LayoutPlan，请先运行视觉编排。"
            )
        layout_plans.append(item.layout_plan)

    renderer = PptxGenPresentationRenderer(resolved, session=session)
    output_dir = renderer.output_dir(presentation_id, version=brief.version)
    _, pptx_path = renderer.render_and_export_pptx_from_layout_plans(
        title=brief.title,
        plans=layout_plans,
        design_system=design,
        output_dir=output_dir,
        slides=slides,
        project_id=presentation.project_id,
    )
    return RenderResult(editable_pptx_path=pptx_path)


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

    preview_by_index = _preview_pngs_by_order(preview_paths or [])

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


def _preview_pngs_by_order(render_paths: list[str]) -> dict[int, str]:
    """Map 0-based slide index → slide_NN.png path from workflow render_paths."""
    from pathlib import Path

    previews = sorted(
        [
            path
            for path in render_paths
            if path.lower().endswith(".png")
            and (
                "slide_preview" in path.replace("\\", "/").lower()
                or Path(path).name.lower().startswith("slide_")
            )
        ],
        key=lambda value: Path(value).name,
    )
    return {index: path for index, path in enumerate(previews)}


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
    presentations = PresentationRepository(session)
    plans = LayoutPlanRepository(session)
    slide = presentations.get_slide(slide_id)
    plan = plans.get(layout_plan_id)
    if slide is None:
        raise ValueError(f"Slide {slide_id} not found")
    if plan is None:
        raise ValueError(f"LayoutPlan {layout_plan_id} not found")
    if plan.slide_id != slide_id:
        raise ValueError("LayoutPlan does not belong to this slide")
    if not get_layout_family_registry().get(plan.layout_family).implemented:
        raise WorkflowError(
            f"版式族「{plan.layout_family.value}」尚未实现 generator，暂不可选用。"
            "请在界面中选择已可用版式，或等待后续版本支持。"
        )
    slide.layout_plan_id = plan.id
    presentations.save_slide(slide)
    return plan


_PRESET_FAMILY: dict[str, LayoutFamily] = {
    "drawing_focus": LayoutFamily.DRAWING_FOCUS,
    "evidence_board": LayoutFamily.EVIDENCE_BOARD,
    "hero": LayoutFamily.HERO,
    "textual_argument": LayoutFamily.TEXTUAL_ARGUMENT,
    "strategy_cards": LayoutFamily.STRATEGY_CARDS,
    "comparative_matrix": LayoutFamily.COMPARATIVE_MATRIX,
}


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

    intent = _apply_preset(intent, preset)
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
    candidates = planner.generate_candidates(
        slide=slide,
        visual_intent_id=intent.id,
        art_direction_id=art.id if art else None,
        design_system_id=design.id,
        candidate_count=candidate_count,
    )
    saved_candidates: list[LayoutPlan] = []
    for plan, _report in candidates:
        saved_candidates.append(plans.save(plan))
    best = planner.select_best(candidates)
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


def _apply_preset(intent: VisualIntent, preset: str | None) -> VisualIntent:
    if not preset:
        return intent
    updates: dict[str, object] = {}
    if preset == "reduce_text":
        updates["density_level"] = DensityLevel.SPACIOUS
        updates["composition_strategy"] = "减少文字，突出主信息"
    elif preset == "enlarge_hero":
        updates["composition_strategy"] = "放大主图，压缩辅助文字"
        updates["density_level"] = DensityLevel.SPACIOUS
    elif preset == "more_whitespace":
        updates["density_level"] = DensityLevel.SPACIOUS
        updates["composition_strategy"] = "增加留白，降低信息密度"
    elif preset == "drawing_focus":
        updates["preferred_layout_families"] = [LayoutFamily.DRAWING_FOCUS]
        updates["dominant_content_type"] = VisualContentType.SITE_PLAN
        updates["image_treatment"] = "drawing_contain"
        updates["composition_strategy"] = "图纸优先"
    elif preset in _PRESET_FAMILY:
        family = _PRESET_FAMILY[preset]
        updates["preferred_layout_families"] = [family]
        updates["composition_strategy"] = f"切换到 {family.value}"
    if not updates:
        return intent
    updated = intent.model_copy(update={**updates, "version": intent.version + 1})
    updated.approval_status = ApprovalStatus.PENDING
    updated.touch()
    return updated
