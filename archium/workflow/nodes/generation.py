"""Generation workflow nodes — brief, storyline, slides, citations, assets."""

from __future__ import annotations

from typing import cast
from uuid import UUID

from archium.agents._helpers import build_project_context_bundle, build_retrieval_query_from_request
from archium.agents.citations import enrich_slide_citations
from archium.application.asset_matching_service import AssetMatchingService
from archium.domain.enums import ApprovalStatus, WorkflowStep
from archium.domain.outline import OutlinePlan
from archium.domain.slide import SlideSpec
from archium.workflow.nodes.base import WorkflowNodeBase
from archium.workflow.state import PresentationWorkflowState


class GenerationNodesMixin(WorkflowNodeBase):
    """Generate presentation content and enrich slides with citations and assets."""

    def generate_brief(self, state: PresentationWorkflowState) -> PresentationWorkflowState:
        logger = self._logger(state)
        if state.get("errors"):
            return {"current_step": WorkflowStep.BRIEF.value}

        existing = state.get("brief")
        if existing is not None:
            refreshed = self._presentations.get_brief(existing.id)
            if refreshed is not None:
                return {"brief": refreshed, "current_step": WorkflowStep.BRIEF.value}

        try:
            project_id = UUID(state["project_id"])
            presentation_id = UUID(state["presentation_id"])
            request = state["request"]
            brief = self._runtime.presentation_service.generate_brief(
                project_id,
                presentation_id,
                request,
            )
            if state.get("require_brief_review"):
                brief.approval_status = ApprovalStatus.PENDING
            else:
                brief.approve()
            brief = self._presentations.save_brief(brief)

            next_state: PresentationWorkflowState = {
                "brief": brief,
                "current_step": WorkflowStep.BRIEF.value,
            }
            merged = cast(PresentationWorkflowState, {**state, **next_state})
            self._persist_checkpoint(merged)
            logger.info("Brief generated for presentation %s", presentation_id)
            return next_state
        except Exception as exc:
            logger.exception("Brief generation failed: %s", exc)
            return {
                "errors": [str(exc)],
                "current_step": WorkflowStep.BRIEF.value,
            }

    def generate_storyline(self, state: PresentationWorkflowState) -> PresentationWorkflowState:
        logger = self._logger(state)
        if state.get("errors"):
            return {"current_step": WorkflowStep.STORYLINE.value}

        existing = state.get("storyline")
        if existing is not None:
            refreshed = self._presentations.get_storyline(existing.id)
            if refreshed is not None:
                return {"storyline": refreshed, "current_step": WorkflowStep.STORYLINE.value}

        brief = state.get("brief")
        if brief is None:
            return {
                "errors": ["Cannot generate storyline without brief"],
                "current_step": WorkflowStep.STORYLINE.value,
            }

        try:
            project_id = UUID(state["project_id"])
            storyline = self._runtime.presentation_service.generate_storyline(project_id, brief)
            if state.get("require_storyline_review"):
                storyline.approval_status = ApprovalStatus.PENDING
            else:
                storyline.approve()
            storyline = self._presentations.save_storyline(storyline)

            next_state: PresentationWorkflowState = {
                "storyline": storyline,
                "current_step": WorkflowStep.STORYLINE.value,
            }
            merged = cast(PresentationWorkflowState, {**state, **next_state})
            self._persist_checkpoint(merged)
            logger.info("Storyline generated for presentation %s", state["presentation_id"])
            return next_state
        except Exception as exc:
            logger.exception("Storyline generation failed: %s", exc)
            return {
                "errors": [str(exc)],
                "current_step": WorkflowStep.STORYLINE.value,
            }

    def generate_outline(self, state: PresentationWorkflowState) -> PresentationWorkflowState:
        logger = self._logger(state)
        if state.get("errors"):
            return {"current_step": WorkflowStep.OUTLINE.value}

        existing = state.get("outline")
        if existing is not None:
            refreshed = self._presentations.get_outline(existing.id)
            if refreshed is not None:
                return {"outline": refreshed, "current_step": WorkflowStep.OUTLINE.value}

        brief = state.get("brief")
        storyline = state.get("storyline")
        if brief is None or storyline is None:
            return {
                "errors": ["Cannot generate outline without brief and storyline"],
                "current_step": WorkflowStep.OUTLINE.value,
            }

        try:
            project_id = UUID(state["project_id"])
            outline = self._runtime.presentation_service.generate_outline_plan(
                project_id,
                brief,
                storyline,
            )
            if state.get("require_outline_review"):
                outline.approval_status = ApprovalStatus.PENDING
            else:
                outline.approve()
            outline = self._presentations.save_outline(outline)

            next_state: PresentationWorkflowState = {
                "outline": outline,
                "current_step": WorkflowStep.OUTLINE.value,
            }
            merged = cast(PresentationWorkflowState, {**state, **next_state})
            self._persist_checkpoint(merged)
            logger.info("Outline generated for presentation %s", state["presentation_id"])
            return next_state
        except Exception as exc:
            logger.exception("Outline generation failed: %s", exc)
            return {
                "errors": [str(exc)],
                "current_step": WorkflowStep.OUTLINE.value,
            }

    def generate_slides(self, state: PresentationWorkflowState) -> PresentationWorkflowState:
        logger = self._logger(state)
        if state.get("errors"):
            return {"current_step": WorkflowStep.SLIDES.value}

        presentation_id = UUID(state["presentation_id"])
        existing = state.get("slides") or []
        if existing:
            slides = self._presentations.list_slides(presentation_id)
            if slides:
                return {"slides": slides, "current_step": WorkflowStep.SLIDES.value}

        brief = state.get("brief")
        storyline = state.get("storyline")
        outline = state.get("outline")
        if brief is None or storyline is None:
            return {
                "errors": ["Cannot generate slides without brief and storyline"],
                "current_step": WorkflowStep.SLIDES.value,
            }
        if outline is None or outline.approval_status != ApprovalStatus.APPROVED:
            return {
                "errors": ["Cannot generate slides without an approved outline plan"],
                "current_step": WorkflowStep.SLIDES.value,
            }

        try:
            project_id = UUID(state["project_id"])
            slides = self._runtime.presentation_service.generate_slide_plan(
                project_id,
                brief,
                storyline,
                outline=outline,
            )
            reviewed_slides: list[SlideSpec] = []
            for slide in slides:
                if state.get("require_slides_review"):
                    slide.mark_planned()
                else:
                    slide.approve()
                reviewed_slides.append(self._presentations.save_slide(slide))

            next_state: PresentationWorkflowState = {
                "slides": reviewed_slides,
                "current_step": WorkflowStep.SLIDES.value,
            }
            merged = cast(PresentationWorkflowState, {**state, **next_state})
            self._persist_checkpoint(merged)
            logger.info(
                "Slide plan generated for presentation %s (%d slides)",
                state["presentation_id"],
                len(reviewed_slides),
            )
            return next_state
        except Exception as exc:
            logger.exception("Slide planning failed: %s", exc)
            return {
                "errors": [str(exc)],
                "current_step": WorkflowStep.SLIDES.value,
            }

    def resolve_citations(self, state: PresentationWorkflowState) -> PresentationWorkflowState:
        logger = self._logger(state)
        if state.get("errors"):
            return {"current_step": WorkflowStep.RESOLVE_CITATIONS.value}

        slides = self._load_slides_for_export(state)
        if not slides:
            return {"current_step": WorkflowStep.RESOLVE_CITATIONS.value}

        try:
            project_id = UUID(state["project_id"])
            bundle = state.get("context_bundle")
            if bundle is None:
                request = state["request"]
                query = build_retrieval_query_from_request(request)
                bundle = build_project_context_bundle(
                    self._runtime.session,
                    project_id,
                    query=query,
                    settings=self._runtime.settings,
                )

            resolved: list[SlideSpec] = []
            for slide in slides:
                enrich_slide_citations(
                    slide,
                    session=self._runtime.session,
                    project_id=project_id,
                    context_bundle=bundle,
                    settings=self._runtime.settings,
                )
                resolved.append(self._presentations.save_slide(slide))

            next_state: PresentationWorkflowState = {
                "slides": resolved,
                "current_step": WorkflowStep.RESOLVE_CITATIONS.value,
            }
            merged = cast(PresentationWorkflowState, {**state, **next_state})
            self._persist_checkpoint(merged)
            logger.info("Resolved citations for %d slides", len(resolved))
            return next_state
        except Exception as exc:
            logger.exception("Citation resolution failed: %s", exc)
            return {
                "errors": [str(exc)],
                "current_step": WorkflowStep.RESOLVE_CITATIONS.value,
            }

    def match_assets(self, state: PresentationWorkflowState) -> PresentationWorkflowState:
        logger = self._logger(state)
        if state.get("errors"):
            return {"current_step": WorkflowStep.MATCH_ASSETS.value}

        try:
            project_id = UUID(state["project_id"])
            presentation_id = UUID(state["presentation_id"])
            matcher = AssetMatchingService(self._runtime.session)
            slides, match_count = matcher.match_presentation_slides(project_id, presentation_id)
            next_state: PresentationWorkflowState = {
                "slides": slides,
                "matched_asset_count": match_count,
                "current_step": WorkflowStep.MATCH_ASSETS.value,
            }
            merged = cast(PresentationWorkflowState, {**state, **next_state})
            self._persist_checkpoint(merged)
            logger.info("Matched %d visual assets for presentation %s", match_count, presentation_id)
            return next_state
        except Exception as exc:
            logger.exception("Asset matching failed: %s", exc)
            return {
                "errors": [str(exc)],
                "current_step": WorkflowStep.MATCH_ASSETS.value,
            }
