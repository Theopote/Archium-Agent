"""LangGraph nodes for the visual composition workflow."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast
from uuid import UUID

from langgraph.types import interrupt
from sqlalchemy.orm import Session

from archium.application.pptxgen_renderer_factory import create_pptxgen_renderer
from archium.application.visual.art_direction_service import ArtDirectionService
from archium.application.visual.asset_reference import (
    AssetReferenceContext,
    build_asset_reference_context,
    content_refs_from_plan,
)
from archium.application.visual.deck_qa_service import DeckQAService
from archium.application.visual.enhanced_deck_composition_service import (
    EnhancedDeckCompositionService,
)
from archium.application.visual.layout_locked import preserve_locked_elements
from archium.application.visual.layout_planning_service import (
    LayoutPlanningService,
    capacity_blocker_messages,
    format_layout_decision_warnings,
)
from archium.application.visual.layout_repair_service import LayoutRepairService
from archium.application.visual.layout_validation_service import LayoutValidationService
from archium.application.visual.scene_repair_service import SceneRepairService
from archium.application.visual.visual_critic_service import VisualCriticService
from archium.application.visual.visual_intent_service import VisualIntentService
from archium.application.visual.visual_scene_repair_workflow_service import (
    VisualSceneRepairWorkflowService,
)
from archium.application.visual.vision import VisionImageGenerationService
from archium.application.workflow_checkpoint import commit_workflow_checkpoint, finalize_run_state
from archium.config.settings import Settings
from archium.domain.enums import (
    ApprovalStatus,
    VisualWorkflowStep,
    WorkflowStatus,
)
from archium.domain.slide_design_brief import SlideDesignBrief
from archium.domain.visual.deck_composition import DeckCompositionPlan
from archium.domain.visual.enums import LayoutValidationStatus
from archium.domain.visual.layout import LayoutPlan
from archium.domain.visual.preferences import VisualPreferences
from archium.infrastructure.database.repositories import (
    PresentationRepository,
    ProjectRepository,
    WorkflowRunRepository,
)
from archium.infrastructure.database.visual_repositories import (
    ArtDirectionRepository,
    DesignSystemRepository,
    LayoutPlanRepository,
    VisualIntentRepository,
)
from archium.infrastructure.llm.base import LLMProvider
from archium.infrastructure.renderers.pptxgen_renderer import PptxGenPresentationRenderer
from archium.logging import ArchiumLogAdapter, get_logger
from archium.workflow.visual_serialization import snapshot_visual_state
from archium.workflow.visual_state import VisualWorkflowState
from archium.workflow.visual_validation_routing import (
    format_blocking_warnings,
    report_has_blocking_issues,
    reports_blocking_summary,
)


def composition_plan_from_state(state: VisualWorkflowState) -> DeckCompositionPlan | None:
    """Normalize deck composition plan from graph state or persisted snapshot."""
    plan = state.get("deck_composition_plan")
    if plan is None:
        return None
    if isinstance(plan, DeckCompositionPlan):
        return plan
    if isinstance(plan, dict):
        return DeckCompositionPlan.model_validate(plan)
    return None


class VisualWorkflowRuntime:
    """Dependencies for visual composition workflow nodes."""

    def __init__(
        self,
        session: Session,
        *,
        settings: Settings,
        llm: LLMProvider | None = None,
        pptxgen_renderer: PptxGenPresentationRenderer | None = None,
    ) -> None:
        self.session = session
        self.settings = settings
        self.llm = llm
        self.projects = ProjectRepository(session)
        self.presentations = PresentationRepository(session)
        self.workflow_runs = WorkflowRunRepository(session)
        self.design_systems = DesignSystemRepository(session)
        self.art_directions = ArtDirectionRepository(session)
        self.layout_plans = LayoutPlanRepository(session)
        self.art_direction_service = ArtDirectionService(session, llm=llm)
        self.visual_intent_service = VisualIntentService(session, llm=llm)
        self.vision_image_service = VisionImageGenerationService(session, settings=settings)
        self.layout_planning_service = LayoutPlanningService(
            session, llm=llm, settings=settings
        )
        self.layout_validation_service = LayoutValidationService()
        self.layout_repair_service = LayoutRepairService()
        self.visual_critic_service = VisualCriticService(
            llm=llm,
            llm_enabled=bool(getattr(settings, "visual_critic_llm_enabled", False)),
            llm_model=getattr(settings, "visual_critic_llm_model", None),
        )
        self.deck_qa_service = DeckQAService()
        self.deck_composition_service = EnhancedDeckCompositionService()
        self.scene_repair_workflow_service = VisualSceneRepairWorkflowService(
            session,
            settings=settings,
            scene_repair=SceneRepairService(),
        )
        self.pptxgen_renderer = pptxgen_renderer or create_pptxgen_renderer(
            settings, session=session
        )


class VisualWorkflowNodes:
    """Node implementations for ArtDirection → Layout → Render."""

    def __init__(self, runtime: VisualWorkflowRuntime) -> None:
        self._runtime = runtime

    def _logger(self, state: VisualWorkflowState) -> ArchiumLogAdapter:
        return get_logger(
            __name__,
            operation="visual_workflow",
            workflow_run_id=state.get("workflow_run_id", "-"),
        )

    def _persist(
        self,
        state: VisualWorkflowState,
        *,
        status: WorkflowStatus | None = None,
    ) -> None:
        workflow_run_id = state.get("workflow_run_id")
        if workflow_run_id is None:
            return
        run = self._runtime.workflow_runs.get_by_id(UUID(workflow_run_id))
        if run is None:
            return
        finalize_run_state(run, snapshot_visual_state(state))
        run.errors = list(state.get("errors", []))
        output_files = list(run.output_files)
        for path in state.get("render_paths", []):
            if path and path not in output_files:
                output_files.append(path)
        run.output_files = output_files
        if status is not None:
            run.status = status
        run.touch()
        self._runtime.workflow_runs.update(run)
        commit_workflow_checkpoint(self._runtime.session, self._runtime.settings)

    def _asset_context_for_plan(
        self, state: VisualWorkflowState, plan: LayoutPlan
    ) -> AssetReferenceContext | None:
        project_id_raw = state.get("project_id")
        if not project_id_raw:
            return None
        return build_asset_reference_context(
            self._runtime.session,
            project_id=UUID(str(project_id_raw)),
            content_refs=content_refs_from_plan(plan),
            settings=self._runtime.settings,
        )

    def load_presentation_context(self, state: VisualWorkflowState) -> VisualWorkflowState:
        logger = self._logger(state)
        step = VisualWorkflowStep.VISUAL_LOAD_CONTEXT.value
        try:
            project_id = UUID(state["project_id"])
            presentation_id = UUID(state["presentation_id"])
            project = self._runtime.projects.get_by_id(project_id)
            if project is None:
                return {
                    "errors": [f"Project {project_id} not found"],
                    "current_step": step,
                }
            presentation = self._runtime.presentations.get_presentation(presentation_id)
            if presentation is None:
                return {
                    "errors": [f"Presentation {presentation_id} not found"],
                    "current_step": step,
                }
            if presentation.project_id != project_id:
                return {
                    "errors": ["Presentation does not belong to the given project"],
                    "current_step": step,
                }

            slides = self._runtime.presentations.list_slides(presentation_id)
            if not slides:
                return {
                    "errors": ["Presentation has no slides to compose"],
                    "current_step": step,
                }

            brief = None
            if presentation.current_brief_id is not None:
                brief = self._runtime.presentations.get_brief(presentation.current_brief_id)
            storyline = None
            if presentation.current_storyline_id is not None:
                storyline = self._runtime.presentations.get_storyline(
                    presentation.current_storyline_id
                )

            warnings: list[str] = []
            if brief is None:
                warnings.append("No PresentationBrief found; art direction will use defaults.")
            if storyline is None:
                warnings.append("No Storyline found; pacing context will be limited.")

            output_dir = (
                self._runtime.settings.output_path
                / "visual-composition"
                / str(presentation_id)
                / str(state["workflow_run_id"])
            )
            output_dir.mkdir(parents=True, exist_ok=True)

            next_state: VisualWorkflowState = {
                "presentation": presentation,
                "brief": brief,
                "storyline": storyline,
                "slides": slides,
                "slide_ids": [str(slide.id) for slide in slides],
                "output_dir": str(output_dir),
                "warnings": warnings,
                "current_step": step,
            }
            merged = cast(VisualWorkflowState, {**state, **next_state})
            self._persist(merged)
            logger.info(
                "Loaded presentation context: %s slides for %s",
                len(slides),
                presentation_id,
            )
            return next_state
        except Exception as exc:
            logger.exception("load_presentation_context failed: %s", exc)
            return {"errors": [str(exc)], "current_step": step}

    def load_or_create_design_system(self, state: VisualWorkflowState) -> VisualWorkflowState:
        logger = self._logger(state)
        step = VisualWorkflowStep.VISUAL_LOAD_DESIGN_SYSTEM.value
        if state.get("errors"):
            return {"current_step": step}
        try:
            design_system_id = state.get("design_system_id")
            design = None
            if design_system_id:
                design = self._runtime.design_systems.get(UUID(design_system_id))
            if design is None:
                from archium.domain.visual.defaults import default_presentation_design_system

                design = self._runtime.design_systems.save(default_presentation_design_system())

            # Apply settings thresholds onto a working copy used for this run.
            thresholds = design.thresholds.model_copy(
                update={
                    "min_body_font_pt": self._runtime.settings.layout_min_body_font_pt,
                    "min_caption_font_pt": self._runtime.settings.layout_min_caption_font_pt,
                    "min_source_font_pt": self._runtime.settings.layout_min_source_font_pt,
                    "min_hero_area_ratio": self._runtime.settings.layout_min_hero_area_ratio,
                    "min_whitespace_ratio": self._runtime.settings.layout_min_whitespace_ratio,
                    "max_whitespace_ratio": self._runtime.settings.layout_max_whitespace_ratio,
                }
            )
            design = design.model_copy(update={"thresholds": thresholds})
            design = self._runtime.design_systems.save(design)

            next_state: VisualWorkflowState = {
                "design_system": design,
                "design_system_id": str(design.id),
                "current_step": step,
            }
            merged = cast(VisualWorkflowState, {**state, **next_state})
            self._persist(merged)
            logger.info("DesignSystem ready: %s", design.name)
            return next_state
        except Exception as exc:
            logger.exception("load_or_create_design_system failed: %s", exc)
            return {"errors": [str(exc)], "current_step": step}

    def generate_art_direction(self, state: VisualWorkflowState) -> VisualWorkflowState:
        logger = self._logger(state)
        step = VisualWorkflowStep.VISUAL_GENERATE_ART_DIRECTION.value
        if state.get("errors"):
            return {"current_step": step}
        try:
            preferences = state.get("preferences") or VisualPreferences()
            design_system_id = UUID(state["design_system_id"])
            from archium.infrastructure.database.repositories import ProjectRepository

            profiles = ProjectRepository(self._runtime.session).list_reference_style_profiles(
                UUID(state["project_id"])
            )
            reference_style_profile = profiles[0] if profiles else None
            art = self._runtime.art_direction_service.generate(
                project_id=UUID(state["project_id"]),
                presentation_id=UUID(state["presentation_id"]),
                design_system_id=design_system_id,
                user_preferences=preferences,
                brief=state.get("brief"),
                storyline=state.get("storyline"),
                reference_style_profile=reference_style_profile,
                use_llm=bool(state.get("use_llm", False)),
            )
            if not state.get("require_art_direction_review", True):
                art = self._runtime.art_direction_service.approve(art.id)

            next_state: VisualWorkflowState = {
                "art_direction": art,
                "art_direction_id": str(art.id),
                "current_step": step,
            }
            merged = cast(VisualWorkflowState, {**state, **next_state})
            self._persist(merged)
            logger.info("ArtDirection generated: %s", art.concept_name)
            return next_state
        except Exception as exc:
            logger.exception("generate_art_direction failed: %s", exc)
            return {"errors": [str(exc)], "current_step": step}

    def await_art_direction_approval(self, state: VisualWorkflowState) -> VisualWorkflowState:
        logger = self._logger(state)
        step = VisualWorkflowStep.VISUAL_AWAIT_ART_DIRECTION_APPROVAL.value
        if state.get("errors"):
            return {"current_step": step}

        art_direction_id = state.get("art_direction_id")
        if art_direction_id is None:
            return {
                "errors": ["Missing art_direction_id before approval gate"],
                "current_step": step,
            }

        art = self._runtime.art_directions.get(UUID(art_direction_id))
        if art is not None and art.approval_status == ApprovalStatus.APPROVED:
            next_state: VisualWorkflowState = {
                "art_direction": art,
                "review_gate": None,
                "current_step": step,
            }
            merged = cast(VisualWorkflowState, {**state, **next_state})
            self._persist(merged, status=WorkflowStatus.RUNNING)
            logger.info("ArtDirection already approved; continuing")
            return next_state

        pause_state: VisualWorkflowState = {
            "current_step": step,
            "review_gate": "art_direction",
        }
        merged_pause = cast(VisualWorkflowState, {**state, **pause_state})
        self._persist(merged_pause, status=WorkflowStatus.AWAITING_REVIEW)
        logger.info("Paused for art direction approval")

        interrupt({"gate": "art_direction", "step": step})

        # After resume — reload approval status.
        art = self._runtime.art_directions.get(UUID(art_direction_id))
        if art is None or art.approval_status != ApprovalStatus.APPROVED:
            return {
                "errors": ["ArtDirection was not approved after review"],
                "current_step": step,
                "review_gate": "art_direction",
            }

        resume_state: VisualWorkflowState = {
            "art_direction": art,
            "review_gate": None,
            "current_step": step,
        }
        merged_resume = cast(VisualWorkflowState, {**state, **resume_state})
        self._persist(merged_resume, status=WorkflowStatus.RUNNING)
        logger.info("Resumed after art direction approval")
        return resume_state

    def generate_visual_intents(self, state: VisualWorkflowState) -> VisualWorkflowState:
        logger = self._logger(state)
        step = VisualWorkflowStep.VISUAL_GENERATE_INTENTS.value
        if state.get("errors"):
            return {"current_step": step}
        try:
            slides = list(state.get("slides") or [])
            art = state.get("art_direction")
            briefs_by_slide_id, briefs_by_order = self._load_design_briefs(
                UUID(str(state["presentation_id"]))
            )
            project_id = UUID(str(state["project_id"]))
            from archium.application.mission_context_bridge import (
                resolve_project_mission,
                resolve_selected_concept_direction,
            )

            mission = resolve_project_mission(
                self._runtime.session,
                project_id,
                presentation_id=UUID(str(state["presentation_id"])),
            )
            concept_direction = (
                resolve_selected_concept_direction(self._runtime.session, mission.id)
                if mission is not None
                else None
            )
            intent_ids: list[str] = []
            updated_slides = []
            fulfill_warnings: list[str] = []
            for index, slide in enumerate(slides):
                previous = slides[index - 1] if index > 0 else None
                nxt = slides[index + 1] if index + 1 < len(slides) else None
                brief = briefs_by_slide_id.get(slide.id) or briefs_by_order.get(slide.order)
                intent = self._runtime.visual_intent_service.generate_for_slide(
                    slide,
                    art_direction=art,
                    previous_slide=previous,
                    next_slide=nxt,
                    design_brief=brief,
                    use_llm=bool(state.get("use_llm", False)),
                )
                intent, image_warnings = (
                    self._runtime.vision_image_service.fulfill_intent_image_request(
                        intent,
                        project_id=project_id,
                        slide_title=slide.title or "",
                        slide_message=slide.message or "",
                        page_archetype=(
                            intent.page_archetype.value
                            if intent.page_archetype is not None
                            else (
                                slide.page_archetype.value
                                if slide.page_archetype is not None
                                else ""
                            )
                        ),
                        direction=concept_direction,
                    )
                )
                for item in image_warnings:
                    fulfill_warnings.append(f"slide {slide.order}: {item}")
                slide.visual_intent_id = intent.id
                self._runtime.presentations.save_slide(slide)
                intent_ids.append(str(intent.id))
                updated_slides.append(slide)

            next_state: VisualWorkflowState = {
                "slides": updated_slides,
                "visual_intent_ids": intent_ids,
                "current_step": step,
            }
            if fulfill_warnings:
                next_state["warnings"] = fulfill_warnings
            merged = cast(VisualWorkflowState, {**state, **next_state})
            self._persist(merged)
            logger.info("Generated %s visual intents", len(intent_ids))
            return next_state
        except Exception as exc:
            logger.exception("generate_visual_intents failed: %s", exc)
            return {"errors": [str(exc)], "current_step": step}

    def _load_design_briefs(
        self, presentation_id: UUID
    ) -> tuple[dict[UUID, SlideDesignBrief], dict[int, SlideDesignBrief]]:
        by_slide: dict[UUID, SlideDesignBrief] = {}
        by_order: dict[int, SlideDesignBrief] = {}
        presentation = self._runtime.presentations.get_presentation(presentation_id)
        if presentation is None or presentation.current_outline_id is None:
            return by_slide, by_order
        outline = self._runtime.presentations.get_outline(presentation.current_outline_id)
        if outline is None:
            return by_slide, by_order
        usable = {ApprovalStatus.APPROVED, ApprovalStatus.PENDING}
        for brief in outline.page_design_briefs:
            if brief.status not in usable:
                continue
            if brief.slide_id is not None:
                by_slide[brief.slide_id] = brief
            by_order[brief.page_order] = brief
        return by_slide, by_order

    def generate_deck_composition_plan(self, state: VisualWorkflowState) -> VisualWorkflowState:
        logger = self._logger(state)
        step = VisualWorkflowStep.VISUAL_GENERATE_DECK_COMPOSITION.value
        if state.get("errors"):
            return {"current_step": step}
        try:
            slides = sorted(list(state.get("slides") or []), key=lambda item: item.order)
            art = state.get("art_direction")
            art_id = state.get("art_direction_id")
            if art is None or art_id is None:
                return {"errors": ["ArtDirection missing"], "current_step": step}

            intents = []
            for slide in slides:
                if slide.visual_intent_id is None:
                    return {
                        "errors": [f"Slide {slide.id} is missing visual_intent_id"],
                        "current_step": step,
                    }
                intent = VisualIntentRepository(self._runtime.session).get(
                    slide.visual_intent_id
                )
                if intent is None:
                    return {
                        "errors": [f"VisualIntent {slide.visual_intent_id} not found"],
                        "current_step": step,
                    }
                intents.append(intent)

            plan = self._runtime.deck_composition_service.plan(
                presentation_id=UUID(str(state["presentation_id"])),
                art_direction_id=UUID(art_id),
                slides=slides,
                visual_intents=intents,
                art_direction=art,
                auto_approve=True,
            )

            output_dir = Path(state.get("output_dir") or ".")
            output_dir.mkdir(parents=True, exist_ok=True)
            plan_path = output_dir / "deck_composition_plan.json"
            plan_path.write_text(
                json.dumps(plan.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            next_state: VisualWorkflowState = {
                "deck_composition_plan_id": str(plan.id),
                "deck_composition_plan": plan,
                "current_step": step,
            }
            render_paths = list(state.get("render_paths") or [])
            render_paths.append(str(plan_path))
            next_state["render_paths"] = render_paths
            merged = cast(VisualWorkflowState, {**state, **next_state})
            self._persist(merged)
            logger.info(
                "Generated deck composition plan with %s slide directives",
                len(plan.slide_directives),
            )
            return next_state
        except Exception as exc:
            logger.exception("generate_deck_composition_plan failed: %s", exc)
            return {"errors": [str(exc)], "current_step": step}

    def generate_layout_candidates(self, state: VisualWorkflowState) -> VisualWorkflowState:
        logger = self._logger(state)
        step = VisualWorkflowStep.VISUAL_GENERATE_LAYOUT_CANDIDATES.value
        if state.get("errors"):
            return {"current_step": step}
        try:
            slides = sorted(list(state.get("slides") or []), key=lambda item: item.order)
            art_id = state.get("art_direction_id")
            design_id = UUID(state["design_system_id"])
            candidate_count = int(state.get("candidate_count", 3))
            composition_plan = composition_plan_from_state(state)
            by_slide: dict[str, list[str]] = {}
            decision_warnings: list[str] = []

            for slide in slides:
                if slide.visual_intent_id is None:
                    return {
                        "errors": [f"Slide {slide.id} is missing visual_intent_id"],
                        "current_step": step,
                    }
                directive = (
                    composition_plan.directive_for_slide(slide.id)
                    if composition_plan is not None
                    else None
                )
                previous_plan = None
                if slide.layout_plan_id is not None:
                    previous_plan = self._runtime.layout_plans.get(slide.layout_plan_id)
                candidates = self._runtime.layout_planning_service.generate_candidates(
                    slide=slide,
                    visual_intent_id=slide.visual_intent_id,
                    art_direction_id=UUID(art_id) if art_id else None,
                    design_system_id=design_id,
                    candidate_count=candidate_count,
                    project_id=UUID(str(state["project_id"]))
                    if state.get("project_id")
                    else None,
                    deck_directive=directive,
                    previous_layout_plan=previous_plan,
                )
                drained = self._runtime.layout_planning_service.drain_warnings()
                decision_warnings.extend(format_layout_decision_warnings(drained))
                blockers = capacity_blocker_messages(drained)
                if blockers:
                    return {
                        "errors": blockers,
                        "warnings": list(dict.fromkeys(decision_warnings)),
                        "current_step": step,
                    }
                ids: list[str] = []
                for plan, _report in candidates:
                    saved = self._runtime.layout_plans.save(plan)
                    ids.append(str(saved.id))
                by_slide[str(slide.id)] = ids

            next_state: VisualWorkflowState = {
                "candidate_plan_ids_by_slide": by_slide,
                "current_step": step,
            }
            if decision_warnings:
                # Dedupe while preserving order (same LLM outage across slides).
                next_state["warnings"] = list(dict.fromkeys(decision_warnings))
            merged = cast(VisualWorkflowState, {**state, **next_state})
            self._persist(merged)
            logger.info("Generated layout candidates for %s slides", len(by_slide))
            return next_state
        except Exception as exc:
            logger.exception("generate_layout_candidates failed: %s", exc)
            return {"errors": [str(exc)], "current_step": step}

    def select_layouts(self, state: VisualWorkflowState) -> VisualWorkflowState:
        logger = self._logger(state)
        step = VisualWorkflowStep.VISUAL_SELECT_LAYOUTS.value
        if state.get("errors"):
            return {"current_step": step}
        try:
            design = state.get("design_system")
            if design is None:
                return {"errors": ["DesignSystem missing"], "current_step": step}

            by_slide = dict(state.get("candidate_plan_ids_by_slide") or {})
            composition_plan = composition_plan_from_state(state)
            selected_ids: list[str] = []
            updated_slides = []
            previous_plan: LayoutPlan | None = None
            for slide in sorted(list(state.get("slides") or []), key=lambda item: item.order):
                candidate_ids = by_slide.get(str(slide.id), [])
                pairs = []
                for plan_id in candidate_ids:
                    plan = self._runtime.layout_plans.get(UUID(plan_id))
                    if plan is None:
                        continue
                    drawing = False
                    # Prefer family-based drawing flag from plan content types.
                    drawing = any(
                        el.content_type.value == "drawing" for el in plan.elements
                    )
                    report = self._runtime.layout_validation_service.validate(
                        plan,
                        design,
                        require_source=True,
                        drawing_hero=drawing
                        or plan.layout_family.value == "drawing_focus",
                        asset_context=self._asset_context_for_plan(state, plan),
                    )
                    pairs.append((plan, report))
                if not pairs:
                    return {
                        "errors": [f"No layout candidates for slide {slide.id}"],
                        "current_step": step,
                    }
                directive = (
                    composition_plan.directive_for_slide(slide.id)
                    if composition_plan is not None
                    else None
                )
                art = state.get("art_direction")
                project_id = (
                    UUID(str(state["project_id"])) if state.get("project_id") else None
                )
                style_preference = (
                    self._runtime.layout_planning_service.resolve_style_preference(
                        project_id=project_id,
                        art_direction=art,
                    )
                )
                best = self._runtime.layout_planning_service.select_best_for_deck(
                    pairs,
                    deck_directive=directive,
                    previous_layout_plan=previous_plan,
                    style_preference=style_preference,
                )
                saved = self._runtime.layout_plans.save(best)
                previous_plan = saved
                slide.layout_plan_id = saved.id
                self._runtime.presentations.save_slide(slide)
                selected_ids.append(str(saved.id))
                updated_slides.append(slide)

            next_state: VisualWorkflowState = {
                "slides": updated_slides,
                "layout_plan_ids": selected_ids,
                "current_step": step,
            }
            merged = cast(VisualWorkflowState, {**state, **next_state})
            self._persist(merged)
            logger.info("Selected %s layout plans", len(selected_ids))
            return next_state
        except Exception as exc:
            logger.exception("select_layouts failed: %s", exc)
            return {"errors": [str(exc)], "current_step": step}

    def validate_layouts(self, state: VisualWorkflowState) -> VisualWorkflowState:
        logger = self._logger(state)
        step = VisualWorkflowStep.VISUAL_VALIDATE_LAYOUTS.value
        if state.get("errors"):
            return {"current_step": step}
        try:
            design = state.get("design_system")
            if design is None:
                return {"errors": ["DesignSystem missing"], "current_step": step}

            reports: list[dict] = []
            for plan_id in state.get("layout_plan_ids", []):
                plan = self._runtime.layout_plans.get(UUID(plan_id))
                if plan is None:
                    reports.append(
                        {
                            "layout_plan_id": plan_id,
                            "valid": False,
                            "score": 0.0,
                            "issues": [
                                {
                                    "rule_code": "LAYOUT.MISSING_PLAN",
                                    "severity": "critical",
                                    "message": "Layout plan not found",
                                }
                            ],
                        }
                    )
                    continue
                drawing = plan.layout_family.value == "drawing_focus" or any(
                    el.content_type.value == "drawing" for el in plan.elements
                )
                report = self._runtime.layout_validation_service.validate(
                    plan,
                    design,
                    require_source=True,
                    drawing_hero=drawing,
                    asset_context=self._asset_context_for_plan(state, plan),
                )
                plan.validation_status = (
                    LayoutValidationStatus.VALID
                    if report.valid
                    else LayoutValidationStatus.INVALID
                )
                self._runtime.layout_plans.save(plan)
                payload = report.model_dump(mode="json")
                payload["layout_plan_id"] = plan_id
                payload["slide_id"] = str(plan.slide_id)
                reports.append(payload)

            next_state: VisualWorkflowState = {
                "validation_reports": reports,
                "current_step": step,
            }
            summary = reports_blocking_summary(reports)
            if summary["warning_only"]:
                next_state["warnings"] = [
                    "Layout validation produced warnings only; proceeding to render."
                ]
            merged = cast(VisualWorkflowState, {**state, **next_state})
            self._persist(merged)
            invalid = sum(1 for item in reports if not item.get("valid", False))
            logger.info(
                "Validated layouts: %s invalid of %s (blocking=%s)",
                invalid,
                len(reports),
                summary["blocking_count"],
            )
            return next_state
        except Exception as exc:
            logger.exception("validate_layouts failed: %s", exc)
            return {"errors": [str(exc)], "current_step": step}

    def repair_layouts(self, state: VisualWorkflowState) -> VisualWorkflowState:
        logger = self._logger(state)
        step = VisualWorkflowStep.VISUAL_REPAIR_LAYOUTS.value
        if state.get("errors"):
            return {"current_step": step}
        try:
            design = state.get("design_system")
            if design is None:
                return {"errors": ["DesignSystem missing"], "current_step": step}

            reports_by_id = {
                str(item.get("layout_plan_id")): item
                for item in state.get("validation_reports", [])
            }
            updated_ids: list[str] = []
            repair_diffs: list[dict] = []
            for plan_id in state.get("layout_plan_ids", []):
                plan = self._runtime.layout_plans.get(UUID(plan_id))
                if plan is None:
                    continue
                raw = reports_by_id.get(plan_id)
                if raw is None or not report_has_blocking_issues(raw):
                    updated_ids.append(plan_id)
                    continue
                from archium.domain.visual.validation import LayoutValidationReport

                filtered = {
                    key: value
                    for key, value in raw.items()
                    if key not in {"layout_plan_id", "slide_id", "valid"}
                }
                report = LayoutValidationReport.model_validate(filtered)
                capacity = None
                try:
                    from archium.application.visual.slide_capacity_service import (
                        SlideCapacityService,
                    )
                    from archium.infrastructure.database.repositories import (
                        PresentationRepository,
                    )
                    from archium.infrastructure.database.visual_repositories import (
                        VisualIntentRepository,
                    )

                    slide = PresentationRepository(self._runtime.session).get_slide(
                        plan.slide_id
                    )
                    if slide is not None and design is not None:
                        intent = VisualIntentRepository(self._runtime.session).get(
                            plan.visual_intent_id
                        )
                        capacity = SlideCapacityService().estimate(
                            slide,
                            design,
                            visual_intent=intent,
                        )
                except Exception:
                    capacity = None
                result = self._runtime.layout_repair_service.repair(
                    plan,
                    report,
                    design,
                    capacity_budget=capacity,
                )
                saved = self._runtime.layout_plans.save(result.plan)
                updated_ids.append(str(saved.id))
                round_index = int(state.get("repair_round", 0)) + 1
                repair_diffs.append(
                    {
                        "round": round_index,
                        **result.to_log_dict(),
                    }
                )
                if not result.reading_order_preserved:
                    logger.warning(
                        "Repair changed reading_order for plan %s (round %s)",
                        plan_id,
                        round_index,
                    )
                logger.info(
                    "Repair diffs for plan %s: %s field changes across %s elements",
                    plan_id,
                    sum(len(d.changed_fields) for d in result.diffs),
                    len(result.diffs),
                )

            next_state: VisualWorkflowState = {
                "layout_plan_ids": updated_ids,
                "repair_round": int(state.get("repair_round", 0)) + 1,
                "repair_diffs": repair_diffs,
                "current_step": step,
            }
            merged = cast(VisualWorkflowState, {**state, **next_state})
            self._persist(merged)
            logger.info("Repaired layouts (round %s)", next_state["repair_round"])
            return next_state
        except Exception as exc:
            logger.exception("repair_layouts failed: %s", exc)
            return {"errors": [str(exc)], "current_step": step}

    def apply_safe_fallback(self, state: VisualWorkflowState) -> VisualWorkflowState:
        """Replace still-blocking plans with the next valid candidate when possible."""
        logger = self._logger(state)
        step = VisualWorkflowStep.VISUAL_APPLY_SAFE_FALLBACK.value
        if state.get("errors"):
            return {"current_step": step}
        try:
            design = state.get("design_system")
            if design is None:
                return {"errors": ["DesignSystem missing"], "current_step": step}

            reports = list(state.get("validation_reports") or [])
            by_slide_candidates = dict(state.get("candidate_plan_ids_by_slide") or {})
            slides = list(state.get("slides") or [])
            selected_ids: list[str] = []
            warnings: list[str] = []
            updated_slides = []

            reports_by_slide = {
                str(item.get("slide_id")): item
                for item in reports
                if item.get("slide_id")
            }

            for slide in slides:
                slide_key = str(slide.id)
                current_id = str(slide.layout_plan_id) if slide.layout_plan_id else None
                report = reports_by_slide.get(slide_key)
                if report is None or not report_has_blocking_issues(report):
                    if current_id:
                        selected_ids.append(current_id)
                    updated_slides.append(slide)
                    continue

                replacement = self._pick_safe_candidate(
                    current_id=current_id,
                    candidate_ids=by_slide_candidates.get(slide_key, []),
                    design=design,
                    state=state,
                )
                if replacement is None:
                    warnings.append(
                        f"No safe fallback candidate for slide {slide_key[:8]}…; "
                        "keeping current plan for layout review."
                    )
                    if current_id:
                        selected_ids.append(current_id)
                    updated_slides.append(slide)
                    continue

                slide.layout_plan_id = replacement.id
                self._runtime.presentations.save_slide(slide)
                selected_ids.append(str(replacement.id))
                updated_slides.append(slide)
                warnings.append(
                    f"Applied safe fallback layout {replacement.layout_family.value} "
                    f"for slide {slide_key[:8]}…"
                )

            next_state: VisualWorkflowState = {
                "slides": updated_slides or slides,
                "layout_plan_ids": selected_ids,
                "fallback_applied": True,
                "warnings": warnings,
                "current_step": step,
            }
            merged = cast(VisualWorkflowState, {**state, **next_state})
            self._persist(merged)
            logger.info("Safe fallback applied for %s slides", len(warnings))
            return next_state
        except Exception as exc:
            logger.exception("apply_safe_fallback failed: %s", exc)
            return {"errors": [str(exc)], "current_step": step}

    def _pick_safe_candidate(
        self,
        *,
        current_id: str | None,
        candidate_ids: list[str],
        design: object,
        state: VisualWorkflowState,
    ) -> LayoutPlan | None:
        from archium.domain.visual.design_system import DesignSystem

        assert isinstance(design, DesignSystem)
        current_plan = (
            self._runtime.layout_plans.get(UUID(current_id)) if current_id else None
        )
        for plan_id in candidate_ids:
            if plan_id == current_id:
                continue
            plan = self._runtime.layout_plans.get(UUID(plan_id))
            if plan is None:
                continue
            drawing = plan.layout_family.value == "drawing_focus" or any(
                el.content_type.value == "drawing" for el in plan.elements
            )
            report = self._runtime.layout_validation_service.validate(
                plan,
                design,
                require_source=True,
                drawing_hero=drawing,
                asset_context=self._asset_context_for_plan(state, plan),
            )
            if report.valid or not any(
                issue.severity.value in {"critical", "error"} for issue in report.issues
            ):
                merged = preserve_locked_elements(plan, current_plan)
                merged.validation_status = (
                    LayoutValidationStatus.VALID
                    if report.valid
                    else LayoutValidationStatus.INVALID
                )
                return self._runtime.layout_plans.save(merged)
        return None

    def await_layout_review(self, state: VisualWorkflowState) -> VisualWorkflowState:
        """Pause when ERROR/CRITICAL issues remain after repair + fallback."""
        logger = self._logger(state)
        step = VisualWorkflowStep.VISUAL_AWAIT_LAYOUT_REVIEW.value
        if state.get("errors"):
            return {"current_step": step}

        reports = list(state.get("validation_reports") or [])
        summary = reports_blocking_summary(reports)
        blocking_notes = format_blocking_warnings(reports)

        pause_state: VisualWorkflowState = {
            "current_step": step,
            "review_gate": "layout_review",
            "warnings": [
                "Layout validation still has ERROR/CRITICAL issues after repair "
                "and safe fallback; paused for user review. PPTX export is blocked."
            ]
            + blocking_notes,
        }
        merged_pause = cast(VisualWorkflowState, {**state, **pause_state})
        self._persist(merged_pause, status=WorkflowStatus.AWAITING_REVIEW)
        logger.info(
            "Paused for layout review (%s blocking plans)",
            summary["blocking_count"],
        )

        decision = interrupt(
            {
                "gate": "layout_review",
                "step": step,
                "blocking_count": summary["blocking_count"],
                "blocking_plan_ids": summary["blocking_plan_ids"],
            }
        )

        # After resume: never silently export invalid PPTX.
        allow_invalid = False
        if isinstance(decision, dict):
            allow_invalid = bool(decision.get("allow_invalid_layout_export", False))

        design = state.get("design_system")
        if design is not None:
            # Re-validate in case the user fixed plans in the UI before continuing.
            refreshed_reports: list[dict] = []
            for plan_id in state.get("layout_plan_ids", []):
                plan = self._runtime.layout_plans.get(UUID(plan_id))
                if plan is None:
                    continue
                drawing = plan.layout_family.value == "drawing_focus" or any(
                    el.content_type.value == "drawing" for el in plan.elements
                )
                report = self._runtime.layout_validation_service.validate(
                    plan,
                    design,
                    require_source=True,
                    drawing_hero=drawing,
                    asset_context=self._asset_context_for_plan(state, plan),
                )
                payload = report.model_dump(mode="json")
                payload["layout_plan_id"] = plan_id
                payload["slide_id"] = str(plan.slide_id)
                refreshed_reports.append(payload)
            reports = refreshed_reports or reports

        still_blocking = reports_blocking_summary(reports)["has_blocking"]
        resume_warnings = list(state.get("warnings") or [])
        export_pptx = bool(state.get("export_pptx", False))
        if still_blocking:
            export_pptx = False
            resume_warnings.append(
                "PPTX export disabled: ERROR/CRITICAL layout issues remain after review."
            )
            if allow_invalid:
                resume_warnings.append(
                    "User acknowledged invalid layouts; continuing with instructions only."
                )

        resume_state: VisualWorkflowState = {
            "validation_reports": reports,
            "review_gate": None,
            "export_pptx": export_pptx,
            "allow_invalid_layout_export": allow_invalid and still_blocking,
            "warnings": resume_warnings,
            "current_step": step,
        }
        merged_resume = cast(VisualWorkflowState, {**state, **resume_state})
        self._persist(merged_resume, status=WorkflowStatus.RUNNING)
        logger.info("Resumed after layout review (still_blocking=%s)", still_blocking)
        return resume_state

    def render_presentation(self, state: VisualWorkflowState) -> VisualWorkflowState:
        logger = self._logger(state)
        step = VisualWorkflowStep.VISUAL_RENDER.value
        if state.get("errors"):
            return {"current_step": step}
        try:
            design = state.get("design_system")
            if design is None:
                return {"errors": ["DesignSystem missing"], "current_step": step}

            output_dir = Path(state.get("output_dir") or ".")
            output_dir.mkdir(parents=True, exist_ok=True)
            render_paths: list[str] = []
            warnings: list[str] = []
            slides = list(state.get("slides") or [])
            plans: list = []
            for plan_id in state.get("layout_plan_ids", []):
                plan = self._runtime.layout_plans.get(UUID(plan_id))
                if plan is not None:
                    plans.append(plan)

            reports = list(state.get("validation_reports") or [])
            blocking = reports_blocking_summary(reports)["has_blocking"]
            export_pptx = bool(state.get("export_pptx", False))
            if blocking and export_pptx:
                export_pptx = False
                warnings.extend(
                    [
                        "Blocked PPTX export: layout still has ERROR/CRITICAL issues.",
                        *format_blocking_warnings(reports),
                    ]
                )

            brief = state.get("brief")
            title = brief.title if brief is not None else "Archium Visual Composition"
            deck = self._runtime.pptxgen_renderer.build_layout_instruction_deck(
                title=title,
                plans=plans,
                design_system=design,
                slides=slides,
                project_id=UUID(state["project_id"]),
            )

            if state.get("export_layout_instructions", True):
                instructions_dir = output_dir / "layout_instructions"
                instructions_dir.mkdir(parents=True, exist_ok=True)
                for index, slide_payload in enumerate(deck.get("slides", []), start=1):
                    family = slide_payload.get("layout_family", "layout")
                    path = instructions_dir / f"slide_{index:02d}_{family}.json"
                    path.write_text(
                        json.dumps(slide_payload, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
                    render_paths.append(str(path))

                deck_path = output_dir / "presentation.layout_instructions.json"
                deck_path.write_text(
                    json.dumps(deck, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                render_paths.append(str(deck_path))

                reports_path = output_dir / "validation_reports.json"
                reports_path.write_text(
                    json.dumps(reports, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                render_paths.append(str(reports_path))

            if export_pptx:
                validation_pptx = bool(
                    getattr(
                        self._runtime.settings,
                        "export_layout_plan_validation_pptx",
                        False,
                    )
                )
                if validation_pptx and plans:
                    from archium.domain.export_authority import (
                        VALIDATION_LAYOUT_PLAN_PPTX_FILENAME,
                    )

                    try:
                        deck_path, pptx_path = (
                            self._runtime.pptxgen_renderer.export_pptx_from_layout_instructions(
                                deck,
                                output_dir=output_dir,
                                pptx_name=VALIDATION_LAYOUT_PLAN_PPTX_FILENAME,
                            )
                        )
                        for path in (deck_path, pptx_path):
                            path_str = str(path)
                            if path_str not in render_paths:
                                render_paths.append(path_str)
                        warnings.append(
                            "Wrote non-formal LayoutPlan validation PPTX "
                            f"({VALIDATION_LAYOUT_PLAN_PPTX_FILENAME}); "
                            "formal delivery is RenderScene → presentation.pptx."
                        )
                    except Exception as pptx_exc:
                        logger.warning(
                            "LayoutPlan validation PPTX export failed (non-fatal): %s",
                            pptx_exc,
                        )
                        warnings.append(
                            f"LayoutPlan validation PPTX export failed: {pptx_exc}"
                        )
                elif export_pptx and not plans:
                    warnings.append(
                        "Skipped formal PPTX export: no LayoutPlan available "
                        "(Scene export runs after compile/repair)."
                    )

            next_state: VisualWorkflowState = {
                "render_paths": render_paths,
                "warnings": warnings,
                "export_pptx": export_pptx,
                "current_step": step,
            }
            merged = cast(VisualWorkflowState, {**state, **next_state})
            self._persist(merged)
            logger.info("Render complete: %s artifacts", len(render_paths))
            return next_state
        except Exception as exc:
            logger.exception("render_presentation failed: %s", exc)
            return {"errors": [str(exc)], "current_step": step}

    def critique_visuals(self, state: VisualWorkflowState) -> VisualWorkflowState:
        """Read-only Visual Critic + Deck QA after render — never repairs/blocks PPTX."""
        logger = self._logger(state)
        step = VisualWorkflowStep.VISUAL_CRITIQUE.value
        if state.get("errors"):
            return {"current_step": step}

        critic_on = bool(getattr(self._runtime.settings, "visual_critic_enabled", True))
        deck_on = bool(getattr(self._runtime.settings, "visual_deck_qa_enabled", True))
        if not critic_on and not deck_on:
            return {
                "current_step": step,
                "visual_critic_reports": [],
                "deck_qa_report": None,
            }

        try:
            plans = []
            for plan_id in state.get("layout_plan_ids", []):
                plan = self._runtime.layout_plans.get(UUID(plan_id))
                if plan is not None:
                    plans.append(plan)

            warnings: list[str] = []
            render_paths = list(state.get("render_paths") or [])
            payloads: list[dict] = []
            deck_payload: dict | None = None
            output_dir = Path(state.get("output_dir") or ".")
            output_dir.mkdir(parents=True, exist_ok=True)

            if critic_on:
                image_paths = self._map_slide_preview_pngs(plans, state.get("render_paths") or [])
                reports = self._runtime.visual_critic_service.evaluate_deck(
                    plans,
                    image_paths=image_paths,
                )
                payloads = [report.model_dump(mode="json") for report in reports]
                for report in reports:
                    for finding in report.findings:
                        warnings.append(
                            f"VisualCritic {finding.rule_code}: {finding.message}"
                        )
                report_path = output_dir / "visual_critic_reports.json"
                report_path.write_text(
                    json.dumps(payloads, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                render_paths.append(str(report_path))
                logger.info(
                    "Visual Critic complete: %s reports (%s findings, %s with images)",
                    len(payloads),
                    sum(len(r.findings) for r in reports),
                    sum(1 for r in reports if r.source_image),
                )

            if deck_on:
                art = state.get("art_direction")
                composition_plan = composition_plan_from_state(state)
                deck_report = self._runtime.deck_qa_service.evaluate(
                    plans,
                    slides=list(state.get("slides") or []),
                    design_system=state.get("design_system"),
                    palette_strategy=(
                        art.palette_strategy if art is not None else None
                    ),
                    composition_plan=composition_plan,
                )
                deck_payload = deck_report.model_dump(mode="json")
                for deck_finding in deck_report.findings:
                    warnings.append(f"DeckQA {deck_finding.rule_code}: {deck_finding.message}")
                deck_path = output_dir / "deck_qa_report.json"
                deck_path.write_text(
                    json.dumps(deck_payload, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                render_paths.append(str(deck_path))
                logger.info(
                    "Deck QA complete: score=%s findings=%s",
                    deck_report.total_score,
                    len(deck_report.findings),
                )

            next_state: VisualWorkflowState = {
                "visual_critic_reports": payloads,
                "deck_qa_report": deck_payload,
                "render_paths": render_paths,
                "warnings": warnings,
                "current_step": step,
            }
            merged = cast(VisualWorkflowState, {**state, **next_state})
            self._persist(merged)
            return next_state
        except Exception as exc:
            # Soft-fail: critic / deck QA must never fail the workflow.
            logger.warning("critique_visuals failed (non-fatal): %s", exc)
            return {
                "current_step": step,
                "warnings": [f"Visual Critic / Deck QA skipped: {exc}"],
            }

    def repair_render_scenes(self, state: VisualWorkflowState) -> VisualWorkflowState:
        """Compile RenderScenes from layout plans and run semantic repair loop."""
        logger = self._logger(state)
        step = VisualWorkflowStep.VISUAL_SCENE_REPAIR.value
        if state.get("errors"):
            return {"current_step": step}

        if not bool(getattr(self._runtime.settings, "scene_repair_enabled", True)):
            return {
                "current_step": step,
                "scene_repair_report": None,
                "warnings": ["Scene repair skipped: scene_repair_enabled=false"],
            }

        design = state.get("design_system")
        slides = list(state.get("slides") or [])
        if design is None or not slides:
            return {
                "current_step": step,
                "warnings": ["Scene repair skipped: missing design system or slides."],
            }

        plans: list[LayoutPlan] = []
        for plan_id in state.get("layout_plan_ids", []):
            plan = self._runtime.layout_plans.get(UUID(plan_id))
            if plan is not None:
                plans.append(plan)
        if not plans:
            return {
                "current_step": step,
                "warnings": ["Scene repair skipped: no layout plans."],
            }

        output_dir = Path(state.get("output_dir") or ".")
        output_dir.mkdir(parents=True, exist_ok=True)
        max_rounds = int(getattr(self._runtime.settings, "scene_repair_max_rounds", 2))
        brief = state.get("brief")
        title = brief.title if brief is not None else "Archium Visual Composition"

        try:
            result = self._runtime.scene_repair_workflow_service.repair_and_persist(
                presentation_id=UUID(state["presentation_id"]),
                project_id=UUID(state["project_id"]),
                slides=slides,
                plans=plans,
                design_system=design,
                output_dir=output_dir,
                max_rounds=max_rounds,
                export_scene_pptx=bool(state.get("export_pptx", False)),
                deck_title=title,
            )
        except Exception as exc:  # noqa: BLE001 — soft-fail like critique
            logger.warning("repair_render_scenes failed (non-fatal): %s", exc)
            return {
                "current_step": step,
                "warnings": [f"Scene repair skipped: {exc}"],
            }

        warnings: list[str] = list(result.warnings)
        render_paths = list(state.get("render_paths") or [])
        render_paths.extend(result.scene_paths)
        formal_pptx_path: str | None = None
        if result.scene_pptx_path:
            formal_pptx_path = result.scene_pptx_path
            render_paths.append(formal_pptx_path)
            if bool(
                getattr(self._runtime.settings, "visual_pptx_screenshots_enabled", True)
            ):
                from archium.infrastructure.renderers.pptx_screenshot import (
                    export_pptx_slide_pngs,
                )

                preview_dir = output_dir / "slide_previews"
                pngs = export_pptx_slide_pngs(Path(formal_pptx_path), preview_dir)
                if pngs:
                    for png in pngs:
                        render_paths.append(str(png))
                else:
                    warnings.append(
                        "PPTX screenshots skipped "
                        "(LibreOffice/pdftoppm unavailable or failed)."
                    )

        report = {
            "scene_count": len(result.scenes),
            "repair_actions": result.repair_actions,
            "repair_rounds": result.repair_rounds,
            "remaining_issue_count": result.remaining_issue_count,
            "scene_paths": result.scene_paths,
            "formal_pptx_path": formal_pptx_path,
            "scene_pptx_path": formal_pptx_path,
        }
        if not result.scenes and plans:
            warnings.append(
                f"Scene repair produced 0 scenes from {len(plans)} layout plan(s)"
            )
        if result.repair_actions:
            warnings.append(
                f"Scene repair applied {result.repair_actions} patch(es) "
                f"in {result.repair_rounds} round(s)"
            )
        if result.remaining_issue_count:
            warnings.append(
                f"Scene repair left {result.remaining_issue_count} repairable issue(s)"
            )

        report_path = output_dir / "scene_repair_report.json"
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        render_paths.append(str(report_path))

        next_state: VisualWorkflowState = {
            "scene_repair_report": report,
            "render_paths": render_paths,
            "warnings": warnings,
            "current_step": step,
        }
        if formal_pptx_path is not None:
            next_state["formal_pptx_path"] = formal_pptx_path
        merged = cast(VisualWorkflowState, {**state, **next_state})
        self._persist(merged)
        logger.info(
            "Scene repair complete: scenes=%s actions=%s rounds=%s",
            len(result.scenes),
            result.repair_actions,
            result.repair_rounds,
        )
        return next_state

    @staticmethod
    def _map_slide_preview_pngs(
        plans: list[LayoutPlan], render_paths: list[str]
    ) -> dict[str, str | Path]:
        """Map layout_plan_id → slide preview PNG from formal Scene PPTX export."""
        previews = sorted(
            [
                Path(raw)
                for raw in render_paths
                if str(raw).lower().endswith(".png")
                and "slide_preview" in str(raw).replace("\\", "/").lower()
                and Path(raw).is_file()
            ],
            key=lambda path: path.name,
        )
        if not previews:
            # Fallback: any slide_XX.png under render_paths.
            previews = sorted(
                [
                    Path(raw)
                    for raw in render_paths
                    if Path(raw).name.lower().startswith("slide_")
                    and Path(raw).suffix.lower() == ".png"
                    and Path(raw).is_file()
                ],
                key=lambda path: path.name,
            )
        mapping: dict[str, str | Path] = {}
        for plan, png in zip(plans, previews, strict=False):
            mapping[str(plan.id)] = png
            mapping[str(plan.slide_id)] = png
        return mapping

    def finalize(self, state: VisualWorkflowState) -> VisualWorkflowState:
        logger = self._logger(state)
        step = VisualWorkflowStep.VISUAL_FINALIZE.value
        errors = list(state.get("errors", []))
        status = WorkflowStatus.FAILED if errors else WorkflowStatus.COMPLETED
        next_state: VisualWorkflowState = {
            "current_step": step,
            "review_gate": None,
        }
        merged = cast(VisualWorkflowState, {**state, **next_state})
        self._persist(merged, status=status)
        logger.info("Visual workflow finalized with status=%s", status.value)
        return next_state
