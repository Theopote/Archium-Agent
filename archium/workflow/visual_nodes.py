"""LangGraph nodes for the visual composition workflow."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast
from uuid import UUID

from langgraph.types import interrupt
from sqlalchemy.orm import Session

from archium.application.visual.art_direction_service import ArtDirectionService
from archium.application.visual.layout_planning_service import LayoutPlanningService
from archium.application.visual.layout_repair_service import LayoutRepairService
from archium.application.visual.layout_validation_service import LayoutValidationService
from archium.application.visual.visual_intent_service import VisualIntentService
from archium.config.settings import Settings
from archium.domain.enums import ApprovalStatus, WorkflowStatus, WorkflowStep
from archium.domain.visual.enums import LayoutValidationStatus
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
)
from archium.infrastructure.llm.base import LLMProvider
from archium.infrastructure.renderers.pptxgen.layout_plan_adapter import (
    PptxLayoutPlanAdapter,
    SlideContentBundle,
)
from archium.infrastructure.renderers.pptxgen_renderer import PptxGenPresentationRenderer
from archium.logging import ArchiumLogAdapter, get_logger
from archium.workflow.visual_serialization import snapshot_visual_state
from archium.workflow.visual_state import VisualWorkflowState


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
        self.layout_planning_service = LayoutPlanningService(session, llm=llm)
        self.layout_validation_service = LayoutValidationService()
        self.layout_repair_service = LayoutRepairService()
        self.layout_plan_adapter = PptxLayoutPlanAdapter()
        self.pptxgen_renderer = pptxgen_renderer or PptxGenPresentationRenderer(
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
        run.state = snapshot_visual_state(state)
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

    def load_presentation_context(self, state: VisualWorkflowState) -> VisualWorkflowState:
        logger = self._logger(state)
        step = WorkflowStep.VISUAL_LOAD_CONTEXT.value
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
        step = WorkflowStep.VISUAL_LOAD_DESIGN_SYSTEM.value
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
        step = WorkflowStep.VISUAL_GENERATE_ART_DIRECTION.value
        if state.get("errors"):
            return {"current_step": step}
        try:
            preferences = state.get("preferences") or VisualPreferences()
            design_system_id = UUID(state["design_system_id"])
            art = self._runtime.art_direction_service.generate(
                project_id=UUID(state["project_id"]),
                presentation_id=UUID(state["presentation_id"]),
                design_system_id=design_system_id,
                user_preferences=preferences,
                brief=state.get("brief"),
                storyline=state.get("storyline"),
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
        step = WorkflowStep.VISUAL_AWAIT_ART_DIRECTION_APPROVAL.value
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
        step = WorkflowStep.VISUAL_GENERATE_INTENTS.value
        if state.get("errors"):
            return {"current_step": step}
        try:
            slides = list(state.get("slides") or [])
            art = state.get("art_direction")
            intent_ids: list[str] = []
            updated_slides = []
            for index, slide in enumerate(slides):
                previous = slides[index - 1] if index > 0 else None
                nxt = slides[index + 1] if index + 1 < len(slides) else None
                intent = self._runtime.visual_intent_service.generate_for_slide(
                    slide,
                    art_direction=art,
                    previous_slide=previous,
                    next_slide=nxt,
                    use_llm=bool(state.get("use_llm", False)),
                )
                slide.visual_intent_id = intent.id
                self._runtime.presentations.save_slide(slide)
                intent_ids.append(str(intent.id))
                updated_slides.append(slide)

            next_state: VisualWorkflowState = {
                "slides": updated_slides,
                "visual_intent_ids": intent_ids,
                "current_step": step,
            }
            merged = cast(VisualWorkflowState, {**state, **next_state})
            self._persist(merged)
            logger.info("Generated %s visual intents", len(intent_ids))
            return next_state
        except Exception as exc:
            logger.exception("generate_visual_intents failed: %s", exc)
            return {"errors": [str(exc)], "current_step": step}

    def generate_layout_candidates(self, state: VisualWorkflowState) -> VisualWorkflowState:
        logger = self._logger(state)
        step = WorkflowStep.VISUAL_GENERATE_LAYOUT_CANDIDATES.value
        if state.get("errors"):
            return {"current_step": step}
        try:
            slides = list(state.get("slides") or [])
            art_id = state.get("art_direction_id")
            design_id = UUID(state["design_system_id"])
            candidate_count = int(state.get("candidate_count", 3))
            by_slide: dict[str, list[str]] = {}

            for slide in slides:
                if slide.visual_intent_id is None:
                    return {
                        "errors": [f"Slide {slide.id} is missing visual_intent_id"],
                        "current_step": step,
                    }
                candidates = self._runtime.layout_planning_service.generate_candidates(
                    slide=slide,
                    visual_intent_id=slide.visual_intent_id,
                    art_direction_id=UUID(art_id) if art_id else None,
                    design_system_id=design_id,
                    candidate_count=candidate_count,
                )
                ids: list[str] = []
                for plan, _report in candidates:
                    saved = self._runtime.layout_plans.save(plan)
                    ids.append(str(saved.id))
                by_slide[str(slide.id)] = ids

            next_state: VisualWorkflowState = {
                "candidate_plan_ids_by_slide": by_slide,
                "current_step": step,
            }
            merged = cast(VisualWorkflowState, {**state, **next_state})
            self._persist(merged)
            logger.info("Generated layout candidates for %s slides", len(by_slide))
            return next_state
        except Exception as exc:
            logger.exception("generate_layout_candidates failed: %s", exc)
            return {"errors": [str(exc)], "current_step": step}

    def select_layouts(self, state: VisualWorkflowState) -> VisualWorkflowState:
        logger = self._logger(state)
        step = WorkflowStep.VISUAL_SELECT_LAYOUTS.value
        if state.get("errors"):
            return {"current_step": step}
        try:
            design = state.get("design_system")
            if design is None:
                return {"errors": ["DesignSystem missing"], "current_step": step}

            by_slide = dict(state.get("candidate_plan_ids_by_slide") or {})
            selected_ids: list[str] = []
            updated_slides = []
            for slide in list(state.get("slides") or []):
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
                    )
                    pairs.append((plan, report))
                if not pairs:
                    return {
                        "errors": [f"No layout candidates for slide {slide.id}"],
                        "current_step": step,
                    }
                best = self._runtime.layout_planning_service.select_best(pairs)
                saved = self._runtime.layout_plans.save(best)
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
        step = WorkflowStep.VISUAL_VALIDATE_LAYOUTS.value
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
            merged = cast(VisualWorkflowState, {**state, **next_state})
            self._persist(merged)
            invalid = sum(1 for item in reports if not item.get("valid", False))
            logger.info("Validated layouts: %s invalid of %s", invalid, len(reports))
            return next_state
        except Exception as exc:
            logger.exception("validate_layouts failed: %s", exc)
            return {"errors": [str(exc)], "current_step": step}

    def repair_layouts(self, state: VisualWorkflowState) -> VisualWorkflowState:
        logger = self._logger(state)
        step = WorkflowStep.VISUAL_REPAIR_LAYOUTS.value
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
            for plan_id in state.get("layout_plan_ids", []):
                plan = self._runtime.layout_plans.get(UUID(plan_id))
                if plan is None:
                    continue
                raw = reports_by_id.get(plan_id)
                if raw is None or raw.get("valid", False):
                    updated_ids.append(plan_id)
                    continue
                from archium.domain.visual.validation import LayoutValidationReport

                filtered = {
                    key: value
                    for key, value in raw.items()
                    if key not in {"layout_plan_id", "slide_id", "valid"}
                }
                report = LayoutValidationReport.model_validate(filtered)
                repaired = self._runtime.layout_repair_service.repair(plan, report, design)
                saved = self._runtime.layout_plans.save(repaired)
                updated_ids.append(str(saved.id))

            next_state: VisualWorkflowState = {
                "layout_plan_ids": updated_ids,
                "repair_round": int(state.get("repair_round", 0)) + 1,
                "current_step": step,
            }
            merged = cast(VisualWorkflowState, {**state, **next_state})
            self._persist(merged)
            logger.info("Repaired layouts (round %s)", next_state["repair_round"])
            return next_state
        except Exception as exc:
            logger.exception("repair_layouts failed: %s", exc)
            return {"errors": [str(exc)], "current_step": step}

    def render_presentation(self, state: VisualWorkflowState) -> VisualWorkflowState:
        logger = self._logger(state)
        step = WorkflowStep.VISUAL_RENDER.value
        if state.get("errors"):
            return {"current_step": step}
        try:
            design = state.get("design_system")
            if design is None:
                return {"errors": ["DesignSystem missing"], "current_step": step}

            output_dir = Path(state.get("output_dir") or ".")
            output_dir.mkdir(parents=True, exist_ok=True)
            render_paths: list[str] = []

            if state.get("export_layout_instructions", True):
                instructions_dir = output_dir / "layout_instructions"
                instructions_dir.mkdir(parents=True, exist_ok=True)
                for index, plan_id in enumerate(state.get("layout_plan_ids", []), start=1):
                    plan = self._runtime.layout_plans.get(UUID(plan_id))
                    if plan is None:
                        continue
                    instruction = self._runtime.layout_plan_adapter.render_slide(
                        plan,
                        design,
                        SlideContentBundle(page_number=index),
                    )
                    path = instructions_dir / f"slide_{index:02d}_{plan.layout_family.value}.json"
                    path.write_text(
                        json.dumps(
                            {
                                "layout_plan_id": str(instruction.layout_plan_id),
                                "design_system_id": str(instruction.design_system_id),
                                "layout_family": instruction.layout_family,
                                "layout_variant": instruction.layout_variant,
                                "page_width": instruction.page_width,
                                "page_height": instruction.page_height,
                                "theme_tokens": instruction.theme_tokens,
                                "elements": instruction.elements,
                            },
                            ensure_ascii=False,
                            indent=2,
                        ),
                        encoding="utf-8",
                    )
                    render_paths.append(str(path))

                reports_path = output_dir / "validation_reports.json"
                reports_path.write_text(
                    json.dumps(state.get("validation_reports", []), ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                render_paths.append(str(reports_path))

            if state.get("export_pptx", False):
                brief = state.get("brief")
                storyline = state.get("storyline")
                slides = list(state.get("slides") or [])
                if brief is None or storyline is None:
                    warnings = [
                        "Skipped PPTX export: brief/storyline missing "
                        "(layout instructions still written)."
                    ]
                    next_partial: VisualWorkflowState = {
                        "render_paths": render_paths,
                        "warnings": warnings,
                        "current_step": step,
                    }
                    merged = cast(VisualWorkflowState, {**state, **next_partial})
                    self._persist(merged)
                    return next_partial

                try:
                    spec_path, pptx_path = self._runtime.pptxgen_renderer.render_and_export_pptx(
                        presentation_id=UUID(state["presentation_id"]),
                        project_id=UUID(state["project_id"]),
                        brief=brief,
                        storyline=storyline,
                        slides=slides,
                        version=brief.version,
                    )
                    render_paths.extend([str(spec_path), str(pptx_path)])
                except Exception as pptx_exc:
                    logger.warning("PPTX export failed (non-fatal): %s", pptx_exc)
                    next_with_warn: VisualWorkflowState = {
                        "render_paths": render_paths,
                        "warnings": [f"PPTX export failed: {pptx_exc}"],
                        "current_step": step,
                    }
                    merged_warn = cast(VisualWorkflowState, {**state, **next_with_warn})
                    self._persist(merged_warn)
                    return next_with_warn

            next_state: VisualWorkflowState = {
                "render_paths": render_paths,
                "current_step": step,
            }
            merged = cast(VisualWorkflowState, {**state, **next_state})
            self._persist(merged)
            logger.info("Render complete: %s artifacts", len(render_paths))
            return next_state
        except Exception as exc:
            logger.exception("render_presentation failed: %s", exc)
            return {"errors": [str(exc)], "current_step": step}

    def finalize(self, state: VisualWorkflowState) -> VisualWorkflowState:
        logger = self._logger(state)
        step = WorkflowStep.VISUAL_FINALIZE.value
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
