"""UI-facing facade for visual composition workflow."""

from __future__ import annotations

import contextlib
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal
from uuid import UUID

from archium.application.design_system_integration import DesignSystemIntegrationService
from archium.application.intelligent_layout import LayoutConsistencyChecker
from archium.application.unit_of_work import SessionLike, api_bound, session_of
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
from archium.domain.export_fidelity import ChartExportMode
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
from archium.infrastructure.database.repositories import WorkflowRunRepository
from archium.infrastructure.layout.layout_family_registry import get_layout_family_registry
from archium.infrastructure.llm.factory import create_llm_provider
from archium.ui.workflow_resources import get_workflow_checkpointer_manager
from archium.ui.workspace_service import _resolve_runtime_settings

logger = logging.getLogger(__name__)

_VISUAL_WORKFLOW_KINDS = frozenset({"visual_composition", "visual"})


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
    session: SessionLike,
    *,
    settings: Settings,
    use_llm: bool,
) -> VisualWorkflowService:
    session = session_of(session)
    llm = create_llm_provider(settings) if use_llm and settings.llm_configured else None
    return VisualWorkflowService(
        session,
        llm=llm,
        settings=settings,
        checkpointer_manager=get_workflow_checkpointer_manager(settings),
    )


def run_visual_workflow(
    session: SessionLike,
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
    session = session_of(session)
    from archium.application.slide_design_brief_service import design_briefs_ready
    from archium.exceptions import WorkflowError

    api = api_bound(session)
    presentation = api.slides.get_presentation(presentation_id)
    if presentation is not None and presentation.current_outline_id is not None:
        outline = api.slides.get_outline(presentation.current_outline_id)
        if outline is not None:
            ready, missing = design_briefs_ready(outline)
            if not ready:
                raise WorkflowError(
                    "视觉版式生成被阻止："
                    + "；".join(missing)
                    + "。请在大纲页完成页面设计摘要批准。"
                )

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
    session: SessionLike,
    workflow_run_id: UUID,
    *,
    approve: bool = True,
    settings: Settings | None = None,
) -> VisualWorkflowResult:
    session = session_of(session)
    resolved = _resolve_runtime_settings(settings)
    service = _create_visual_workflow_service(session, settings=resolved, use_llm=False)
    return service.continue_after_art_direction_approval(
        workflow_run_id,
        approve=approve,
    )


def continue_visual_after_layout_review(
    session: SessionLike,
    workflow_run_id: UUID,
    *,
    allow_invalid_layout_export: bool = False,
    settings: Settings | None = None,
) -> VisualWorkflowResult:
    session = session_of(session)
    resolved = _resolve_runtime_settings(settings)
    service = _create_visual_workflow_service(session, settings=resolved, use_llm=False)
    return service.continue_after_layout_review(
        workflow_run_id,
        allow_invalid_layout_export=allow_invalid_layout_export,
    )


def presentation_has_visual_layout(session: SessionLike, presentation_id: UUID) -> bool:
    """Return True when every slide has a persisted LayoutPlan.

    Implementation lives in application; this UI re-export keeps existing callers stable.
    """
    session = session_of(session)
    from archium.application.visual.layout_readiness import (
        presentation_has_visual_layout as _impl,
    )

    return _impl(session, presentation_id)


def export_presentation_pptx_from_layout_plans(
    session: SessionLike,
    presentation_id: UUID,
    *,
    settings: Settings | None = None,
    chart_export_mode: ChartExportMode | None = None,
) -> RenderResult:
    """Export formal editable PPTX from RenderScenes (DOM-003 authority)."""
    session = session_of(session)
    return api_bound(session).render.export_editable_pptx_result(
        presentation_id,
        chart_export_mode=chart_export_mode,
        allow_legacy_spec_fallback=False,
        settings=_resolve_runtime_settings(settings),
    )


def generate_visual_and_export_pptx(
    session: SessionLike,
    project_id: UUID,
    presentation_id: UUID,
    *,
    settings: Settings | None = None,
) -> VisualWorkflowResult:
    """Run visual composition with PPTX export enabled (streamlined export path)."""
    session = session_of(session)
    return run_visual_workflow(
        session,
        project_id,
        presentation_id,
        require_art_direction_review=True,
        use_llm=False,
        export_pptx=True,
        settings=settings,
    )


def _is_visual_workflow_state(state: dict[str, Any]) -> bool:
    kind = str(state.get("workflow_kind") or "").strip().lower()
    if kind in _VISUAL_WORKFLOW_KINDS:
        return True
    # Legacy / partial snapshots may omit kind but still carry visual QA artifacts.
    return isinstance(state.get("deck_qa_report"), dict) or bool(
        state.get("visual_critic_reports")
    )


def _read_json_dict(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _read_json_list(path: Path) -> list[dict] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, list):
        return None
    return [item for item in payload if isinstance(item, dict)]


def load_persisted_visual_qa_artifacts(
    session: SessionLike,
    presentation_id: UUID,
) -> tuple[list[dict] | None, dict | None, list[str] | None, str | None]:
    """Reload Deck QA / critic / preview paths from the latest visual workflow run.

    Live session state is preferred by callers; this fills the gap after Streamlit
    restart so deliver/studio checklists still see completed QA.
    """
    session = session_of(session)
    runs = WorkflowRunRepository(session).list_by_presentation(presentation_id)
    for run in runs:
        state = dict(run.state or {})
        if not _is_visual_workflow_state(state):
            continue

        deck_qa = state.get("deck_qa_report")
        deck_qa = deck_qa if isinstance(deck_qa, dict) else None
        critics_raw = state.get("visual_critic_reports")
        critics = (
            [item for item in critics_raw if isinstance(item, dict)]
            if isinstance(critics_raw, list)
            else None
        )
        render_paths_raw = state.get("render_paths")
        render_paths = (
            [str(path) for path in render_paths_raw]
            if isinstance(render_paths_raw, list)
            else None
        )
        output_dir_raw = state.get("output_dir")
        output_dir = output_dir_raw if isinstance(output_dir_raw, str) else None

        if deck_qa is None and output_dir:
            deck_qa = _read_json_dict(Path(output_dir) / "deck_qa_report.json")
        if not critics and output_dir:
            critics = _read_json_list(Path(output_dir) / "visual_critic_reports.json")

        if deck_qa is None and not critics and not render_paths:
            continue

        logger.debug(
            "Loaded persisted visual QA for presentation %s from run %s "
            "(deck_qa=%s critics=%s)",
            presentation_id,
            run.id,
            deck_qa is not None,
            len(critics or []),
        )
        return critics, deck_qa, render_paths, output_dir

    return None, None, None, None


def get_presentation_visual_snapshot(
    session: SessionLike,
    presentation_id: UUID,
    *,
    visual_critic_reports: list[dict] | None = None,
    deck_qa_report: dict | None = None,
    preview_paths: list[str] | None = None,
) -> PresentationVisualSnapshot:
    session = session_of(session)
    loaded = api_bound(session).visual.load_presentation_visual(presentation_id)
    design_system = loaded.design_system
    art_direction = loaded.art_direction

    if (
        visual_critic_reports is None
        or deck_qa_report is None
        or preview_paths is None
    ):
        persisted_critics, persisted_deck_qa, persisted_previews, _ = (
            load_persisted_visual_qa_artifacts(session, presentation_id)
        )
        if visual_critic_reports is None:
            visual_critic_reports = persisted_critics
        if deck_qa_report is None:
            deck_qa_report = persisted_deck_qa
        if preview_paths is None:
            preview_paths = persisted_previews

    critic_by_slide: dict[str, dict] = {}
    for report in visual_critic_reports or []:
        slide_key = str(report.get("slide_id") or "")
        if slide_key:
            critic_by_slide[slide_key] = report

    preview_by_index = map_preview_pngs_by_order(preview_paths or [])

    slide_snapshots: list[SlideVisualSnapshot] = []
    validator = LayoutValidationService()
    for index, item in enumerate(loaded.slides):
        slide = item.slide
        plan = item.layout_plan
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
                visual_intent=item.visual_intent,
                layout_plan=plan,
                candidates=item.candidates,
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
    session: SessionLike,
    art_direction_id: UUID,
    updates: dict[str, object],
) -> ArtDirection:
    session = session_of(session)
    return ArtDirectionService(session).update(art_direction_id, updates)


def approve_art_direction(session: SessionLike, art_direction_id: UUID) -> ArtDirection:
    session = session_of(session)
    return ArtDirectionService(session).approve(art_direction_id)


def regenerate_art_direction(
    session: SessionLike,
    art_direction_id: UUID,
    feedback: str,
    *,
    use_llm: bool = False,
    settings: Settings | None = None,
) -> ArtDirection:
    session = session_of(session)
    resolved = _resolve_runtime_settings(settings)
    llm = create_llm_provider(resolved) if use_llm and resolved.llm_configured else None
    return ArtDirectionService(session, llm=llm).regenerate(art_direction_id, feedback)


def select_layout_candidate(
    session: SessionLike,
    *,
    slide_id: UUID,
    layout_plan_id: UUID,
) -> LayoutPlan:
    session = session_of(session)
    from archium.application.visual.layout_locked import preserve_locked_elements
    from archium.application.visual.visual_history_service import VisualHistoryService
    from archium.domain.enums import RevisionSource

    api = api_bound(session)
    visual = api.visual
    slides = api.slides
    slide = slides.get(slide_id)
    plan = visual.get_layout_plan(layout_plan_id)
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
        previous_plan = visual.get_layout_plan(slide.layout_plan_id)
    merged = preserve_locked_elements(plan, previous_plan)
    if merged is not plan:
        merged = visual.save_layout_plan(merged)
        plan = merged
    slide.layout_plan_id = plan.id
    slides.save(slide)

    intent = visual.resolve_visual_intent_for_slide(slide)
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
    session: SessionLike,
    *,
    slide_id: UUID,
    template_id: UUID,
    candidate_count: int = 3,
    settings: Settings | None = None,
) -> SlideVisualSnapshot:
    """Match a published template to the slide, fill content, and select the best plan."""
    session = session_of(session)
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
    api = api_bound(session)
    slide = api.slides.get(slide_id)
    if slide is None:
        raise WorkflowError(f"页面不存在：{slide_id}")
    intent = api.visual.resolve_visual_intent_for_slide(slide)
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
    session: SessionLike,
    *,
    slide_id: UUID,
    preset: str | None = None,
    candidate_count: int = 5,
    use_llm: bool = False,
    settings: Settings | None = None,
    previous_layout_plan: LayoutPlan | None = None,
    recent_layout_plans: list[LayoutPlan] | None = None,
) -> SlideVisualSnapshot:
    """Re-plan a single slide; optional preset tweaks VisualIntent before planning."""
    session = session_of(session)
    resolved = _resolve_runtime_settings(settings)
    api = api_bound(session)
    visual = api.visual
    slides = api.slides

    slide = slides.get(slide_id)
    if slide is None:
        raise ValueError(f"Slide {slide_id} not found")

    intent = visual.resolve_visual_intent_for_slide(slide)
    if intent is None:
        llm = create_llm_provider(resolved) if use_llm and resolved.llm_configured else None
        intent = VisualIntentService(session, llm=llm).generate_for_slide(
            slide, use_llm=use_llm and resolved.llm_configured
        )
        slide.visual_intent_id = intent.id
        slides.save(slide)

    intent = apply_visual_intent_preset(intent, preset)
    intent = visual.save_visual_intent(intent)

    presentation = slides.get_presentation(slide.presentation_id)
    art = None
    design = None
    art_id = intent.art_direction_id
    if art_id is not None:
        art = visual.get_art_direction(art_id)
        if art is not None and art.design_system_id is not None:
            design = visual.get_design_system(art.design_system_id)
    if design is None and presentation is not None:
        art = visual.resolve_art_direction_for_presentation(
            project_id=presentation.project_id,
            presentation_id=slide.presentation_id,
        )
        if art is not None and art.design_system_id is not None:
            design = visual.get_design_system(art.design_system_id)
    if design is None:
        from archium.domain.visual.defaults import default_presentation_design_system

        design = visual.save_design_system(default_presentation_design_system())

    llm = create_llm_provider(resolved) if use_llm and resolved.llm_configured else None
    planner = LayoutPlanningService(session, llm=llm, settings=resolved)
    project_id = presentation.project_id if presentation is not None else None

    # Prefer the caller's prior-slide plan; otherwise resolve the previous ordered slide.
    prior_plan = previous_layout_plan
    recent_plans = list(recent_layout_plans or [])
    if prior_plan is None and presentation is not None:
        ordered = sorted(
            slides.list_for_presentation(slide.presentation_id),
            key=lambda item: item.order,
        )
        for index, item in enumerate(ordered):
            if item.id != slide.id:
                continue
            if index > 0:
                prior_plan = visual.resolve_layout_plan_for_slide(ordered[index - 1])
            if not recent_plans:
                recent_plans = [
                    plan
                    for peer in ordered[:index]
                    if (plan := visual.resolve_layout_plan_for_slide(peer)) is not None
                ]
            break

    from archium.application.visual.deck_composition_service import (
        DeckCompositionPlanningService,
    )

    deck_directive = DeckCompositionPlanningService()._initial_directive(
        index=slide.order,
        slide=slide,
        intent=intent,
        previous=None,
    )

    candidates = planner.generate_candidates(
        slide=slide,
        visual_intent_id=intent.id,
        art_direction_id=art.id if art else None,
        design_system_id=design.id,
        candidate_count=candidate_count,
        project_id=project_id,
        deck_directive=deck_directive,
        previous_layout_plan=prior_plan,
    )
    saved_candidates: list[LayoutPlan] = []
    for plan, _report in candidates:
        saved_candidates.append(visual.save_layout_plan(plan))
    best = planner.select_best_for_deck(
        candidates,
        deck_directive=deck_directive,
        previous_layout_plan=prior_plan,
        recent_layout_plans=recent_plans,
        style_preference=planner.last_style_preference,
    )
    best = visual.save_layout_plan(best)
    slide.layout_plan_id = best.id
    slides.save(slide)

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
        candidates=saved_candidates or visual.list_layout_plans_for_slide(slide.id),
        validation=validation,
    )


def optimize_slide_layout_with_intelligent_algorithm(
    session: SessionLike,
    slide: SlideSpec,
    design_system_integration: DesignSystemIntegrationService,
    constraints: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Optimize slide layout using intelligent layout algorithm.
    
    This function integrates the new intelligent layout optimizer with the
    existing visual workflow to provide enhanced layout recommendations.
    
    Args:
        session: Database session
        slide: Slide specification
        design_system_integration: Design system integration service
        constraints: Optional layout constraints
    
    Returns:
        Layout optimization result with recommended layout and positions
    """
    session = session_of(session)
    # Convert slide data to format expected by intelligent layout optimizer
    slide_data = {
        "id": str(slide.id),
        "title": slide.title,
        "body": slide.message,
        "image": None,
        # Add more slide data as needed
    }
    
    # Get available layouts from design system
    from archium.domain.presentation_templates import SlideLayout
    available_layouts = [
        SlideLayout.TITLE,
        SlideLayout.TITLE_CONTENT,
        SlideLayout.TWO_COLUMN,
        SlideLayout.THREE_COLUMN,
        SlideLayout.IMAGE_TEXT,
        SlideLayout.TEXT_IMAGE,
        SlideLayout.FULL_IMAGE,
    ]
    
    # Optimize layout
    layout_result = design_system_integration.optimize_slide_layout(
        slide_data,
        available_layouts,
        constraints,
    )
    
    return layout_result


def apply_intelligent_layout_to_visual_workflow(
    session: SessionLike,
    presentation_id: UUID,
    slides: list[SlideSpec],
    design_system_integration: DesignSystemIntegrationService,
) -> list[dict[str, Any]]:
    """Apply intelligent layout optimization to entire presentation.
    
    This function applies the intelligent layout algorithm to all slides
    in a presentation to ensure consistency and optimal layouts.
    
    Args:
        session: Database session
        presentation_id: Presentation ID
        slides: List of slide specifications
        design_system_integration: Design system integration service
    
    Returns:
        List of layout optimization results for each slide
    """
    session = session_of(session)
    consistency_checker = LayoutConsistencyChecker()
    
    optimization_results: list[dict[str, Any]] = []
    for i, slide in enumerate(slides):
        # Get previous slides for consistency checking
        previous_slides_data = []
        for prev_slide in slides[:i]:
            previous_slides_data.append({
                "id": str(prev_slide.id),
                "title": prev_slide.title,
                "body": prev_slide.message,
            })
        
        # Optimize current slide
        slide_data = {
            "id": str(slide.id),
            "title": slide.title,
            "body": slide.message,
            "image": None,
        }
        
        layout_result = design_system_integration.optimize_slide_layout(slide_data)
        
        # Check consistency with previous slides
        consistency_report = consistency_checker.check_consistency(
            {"layout": layout_result["recommended_layout"]},
            [{"layout": r["recommended_layout"]} for r in optimization_results],
        )
        
        optimization_results.append({
            "slide_id": str(slide.id),
            "slide_number": i + 1,
            "layout_optimization": layout_result,
            "consistency_report": consistency_report,
        })
    
    return optimization_results

