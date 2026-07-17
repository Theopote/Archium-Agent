"""LangGraph node implementations for the presentation workflow."""

from __future__ import annotations

from typing import cast
from uuid import UUID

from langgraph.types import interrupt

from archium.agents._helpers import build_project_context_bundle, build_retrieval_query_from_request
from archium.agents.citations import enrich_slide_citations
from archium.application.asset_matching_service import AssetMatchingService
from archium.application.automated_review_service import (
    AutomatedReviewService,
    critical_export_block_messages,
)
from archium.application.fact_extraction_service import FactExtractionService
from archium.application.fact_validation_service import FactValidationService
from archium.application.render_export import export_marp_extras, export_pptxgen_extras
from archium.application.review_service import slides_are_approved
from archium.application.slide_repair_service import SlideRepairService
from archium.domain.enums import (
    ApprovalStatus,
    PresentationStatus,
    WorkflowStatus,
    WorkflowStep,
)
from archium.domain.review import ReviewIssue, merge_review_findings
from archium.domain.slide import SlideSpec
from archium.infrastructure.database.repositories import (
    DocumentRepository,
    FactRepository,
    PresentationRepository,
    ProjectRepository,
)
from archium.logging import ArchiumLogAdapter, get_logger
from archium.workflow.runtime import PresentationWorkflowRuntime
from archium.workflow.serialization import snapshot_state
from archium.workflow.state import PresentationWorkflowState


class PresentationWorkflowNodes:
    """Node handlers that delegate to the Stage 6 presentation pipeline."""

    def __init__(self, runtime: PresentationWorkflowRuntime) -> None:
        self._runtime = runtime
        self._presentations = PresentationRepository(runtime.session)

    def _logger(self, state: PresentationWorkflowState) -> ArchiumLogAdapter:
        workflow_run_id = state.get("workflow_run_id", "-")
        return get_logger(
            __name__,
            operation="presentation_workflow",
            workflow_run_id=workflow_run_id,
        )

    @staticmethod
    def _merge_review_findings(
        state: PresentationWorkflowState,
        new_issues: list[ReviewIssue],
        reviewer: AutomatedReviewService,
    ) -> dict[str, object]:
        return merge_review_findings(
            list(state.get("review_issues", [])),
            new_issues,
            reviewer.summarize_for_slides,
        )

    def _persist_checkpoint(
        self,
        state: PresentationWorkflowState,
        *,
        status: WorkflowStatus | None = None,
    ) -> None:
        workflow_run_id = state.get("workflow_run_id")
        if workflow_run_id is None:
            return
        run = self._runtime.workflow_runs.get_by_id(UUID(workflow_run_id))
        if run is None:
            return
        run.state = snapshot_state(state)
        run.errors = list(state.get("errors", []))
        output_files = list(run.output_files)
        json_path = state.get("json_path")
        if json_path and json_path not in output_files:
            output_files.append(json_path)
        marp_md_path = state.get("marp_md_path")
        if marp_md_path and marp_md_path not in output_files:
            output_files.append(marp_md_path)
        marp_pptx_path = state.get("marp_pptx_path")
        if marp_pptx_path and marp_pptx_path not in output_files:
            output_files.append(marp_pptx_path)
        pdf_path = state.get("pdf_path")
        if pdf_path and pdf_path not in output_files:
            output_files.append(pdf_path)
        for preview_path in state.get("preview_image_paths", []):
            if preview_path and preview_path not in output_files:
                output_files.append(preview_path)
        run.output_files = output_files
        if status is not None:
            run.status = status
        run.touch()
        self._runtime.workflow_runs.update(run)

    def load_project(self, state: PresentationWorkflowState) -> PresentationWorkflowState:
        logger = self._logger(state)
        if state.get("errors"):
            return {"current_step": WorkflowStep.LOAD_PROJECT.value}

        try:
            project_id = UUID(state["project_id"])
            project = ProjectRepository(self._runtime.session).get_by_id(project_id)
            if project is None:
                return {
                    "errors": [f"Project {project_id} not found"],
                    "current_step": WorkflowStep.LOAD_PROJECT.value,
                }

            next_state: PresentationWorkflowState = {
                "project_name": project.name,
                "current_step": WorkflowStep.LOAD_PROJECT.value,
            }
            merged = cast(PresentationWorkflowState, {**state, **next_state})
            self._persist_checkpoint(merged)
            logger.info("Loaded project %s (%s)", project_id, project.name)
            return next_state
        except Exception as exc:
            logger.exception("Project load failed: %s", exc)
            return {
                "errors": [str(exc)],
                "current_step": WorkflowStep.LOAD_PROJECT.value,
            }

    def validate_sources(self, state: PresentationWorkflowState) -> PresentationWorkflowState:
        logger = self._logger(state)
        if state.get("errors"):
            return {"current_step": WorkflowStep.VALIDATE_SOURCES.value}

        try:
            project_id = UUID(state["project_id"])
            documents = DocumentRepository(self._runtime.session).list_by_project(project_id)
            chunks = DocumentRepository(self._runtime.session).list_chunks_by_project(project_id)
            issues: list[str] = []
            if not documents:
                issues.append("项目尚未上传任何资料文档")
            elif not chunks:
                issues.append("项目文档尚未完成分块处理")

            next_state: PresentationWorkflowState = {
                "source_document_count": len(documents),
                "source_chunk_count": len(chunks),
                "source_validation_issues": issues,
                "current_step": WorkflowStep.VALIDATE_SOURCES.value,
            }
            merged = cast(PresentationWorkflowState, {**state, **next_state})
            self._persist_checkpoint(merged)
            if issues:
                logger.warning(
                    "Source validation for project %s: %s",
                    project_id,
                    "; ".join(issues),
                )
            else:
                logger.info(
                    "Validated sources for project %s (%d docs, %d chunks)",
                    project_id,
                    len(documents),
                    len(chunks),
                )
            return next_state
        except Exception as exc:
            logger.exception("Source validation failed: %s", exc)
            return {
                "errors": [str(exc)],
                "current_step": WorkflowStep.VALIDATE_SOURCES.value,
            }

    def retrieve_context(self, state: PresentationWorkflowState) -> PresentationWorkflowState:
        logger = self._logger(state)
        if state.get("errors"):
            return {"current_step": WorkflowStep.RETRIEVE_CONTEXT.value}

        existing = state.get("context_bundle")
        if existing is not None and existing.chunks:
            return {"context_bundle": existing, "current_step": WorkflowStep.RETRIEVE_CONTEXT.value}

        try:
            project_id = UUID(state["project_id"])
            request = state["request"]
            query = build_retrieval_query_from_request(request)
            bundle = build_project_context_bundle(
                self._runtime.session,
                project_id,
                query=query,
                settings=self._runtime.settings,
            )
            next_state: PresentationWorkflowState = {
                "context_bundle": bundle,
                "current_step": WorkflowStep.RETRIEVE_CONTEXT.value,
            }
            merged = cast(PresentationWorkflowState, {**state, **next_state})
            self._persist_checkpoint(merged)
            logger.info(
                "Retrieved project context for presentation %s (%d chunks)",
                state["presentation_id"],
                len(bundle.chunks),
            )
            return next_state
        except Exception as exc:
            logger.exception("Context retrieval failed: %s", exc)
            return {
                "errors": [str(exc)],
                "current_step": WorkflowStep.RETRIEVE_CONTEXT.value,
            }

    def extract_facts(self, state: PresentationWorkflowState) -> PresentationWorkflowState:
        logger = self._logger(state)
        if state.get("errors"):
            return {"current_step": WorkflowStep.EXTRACT_FACTS.value}

        try:
            project_id = UUID(state["project_id"])
            facts_repo = FactRepository(self._runtime.session)
            existing_db = facts_repo.list_by_project(project_id)
            if existing_db:
                return {
                    "project_facts": existing_db,
                    "extracted_fact_count": 0,
                    "current_step": WorkflowStep.EXTRACT_FACTS.value,
                }

            extractor = FactExtractionService(
                self._runtime.session,
                llm=self._runtime.llm,
                settings=self._runtime.settings,
            )
            _, created = extractor.extract_from_context(project_id, state.get("context_bundle"))
            facts = facts_repo.list_by_project(project_id)
            next_state: PresentationWorkflowState = {
                "project_facts": facts,
                "extracted_fact_count": created,
                "current_step": WorkflowStep.EXTRACT_FACTS.value,
            }
            merged = cast(PresentationWorkflowState, {**state, **next_state})
            self._persist_checkpoint(merged)
            logger.info("Fact extraction complete for project %s (%d new)", project_id, created)
            return next_state
        except Exception as exc:
            logger.exception("Fact extraction failed: %s", exc)
            return {
                "errors": [str(exc)],
                "current_step": WorkflowStep.EXTRACT_FACTS.value,
            }

    def validate_facts(self, state: PresentationWorkflowState) -> PresentationWorkflowState:
        logger = self._logger(state)
        if state.get("errors"):
            return {"current_step": WorkflowStep.VALIDATE_FACTS.value}

        try:
            project_id = UUID(state["project_id"])
            result = FactValidationService(self._runtime.session).validate(project_id)
            next_state: PresentationWorkflowState = {
                "project_facts": result.facts,
                "fact_validation_issues": result.issues,
                "current_step": WorkflowStep.VALIDATE_FACTS.value,
            }
            merged = cast(PresentationWorkflowState, {**state, **next_state})
            self._persist_checkpoint(merged)
            if result.issues:
                logger.warning(
                    "Fact validation for project %s recorded %d issue(s)",
                    project_id,
                    len(result.issues),
                )
            else:
                logger.info("Fact validation passed for project %s", project_id)
            return next_state
        except Exception as exc:
            logger.exception("Fact validation failed: %s", exc)
            return {
                "errors": [str(exc)],
                "current_step": WorkflowStep.VALIDATE_FACTS.value,
            }

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
        if brief is None or storyline is None:
            return {
                "errors": ["Cannot generate slides without brief and storyline"],
                "current_step": WorkflowStep.SLIDES.value,
            }

        try:
            project_id = UUID(state["project_id"])
            slides = self._runtime.presentation_service.generate_slide_plan(
                project_id,
                brief,
                storyline,
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

    def run_content_review(self, state: PresentationWorkflowState) -> PresentationWorkflowState:
        logger = self._logger(state)
        if state.get("errors"):
            return {"current_step": WorkflowStep.CONTENT_REVIEW.value}

        slides = self._load_slides_for_export(state)
        if not slides:
            return {"current_step": WorkflowStep.CONTENT_REVIEW.value}

        try:
            presentation_id = UUID(state["presentation_id"])
            reviewer = AutomatedReviewService(
                self._runtime.session,
                llm=self._runtime.llm,
                settings=self._runtime.settings,
            )
            content_issues = reviewer.run_content_review(
                presentation_id,
                slides,
                brief=state.get("brief"),
            )
            next_state = cast(
                PresentationWorkflowState,
                {
                    **self._merge_review_findings(state, content_issues, reviewer),
                    "current_step": WorkflowStep.CONTENT_REVIEW.value,
                },
            )
            merged = cast(PresentationWorkflowState, {**state, **next_state})
            self._persist_checkpoint(merged)
            logger.info("Content review recorded %d issue(s)", len(content_issues))
            return next_state
        except Exception as exc:
            logger.exception("Content review failed: %s", exc)
            return {
                "errors": [str(exc)],
                "current_step": WorkflowStep.CONTENT_REVIEW.value,
            }

    def run_evidence_review(self, state: PresentationWorkflowState) -> PresentationWorkflowState:
        logger = self._logger(state)
        if state.get("errors"):
            return {"current_step": WorkflowStep.EVIDENCE_REVIEW.value}

        slides = self._load_slides_for_export(state)
        if not slides:
            return {"current_step": WorkflowStep.EVIDENCE_REVIEW.value}

        try:
            presentation_id = UUID(state["presentation_id"])
            reviewer = AutomatedReviewService(
                self._runtime.session,
                llm=self._runtime.llm,
                settings=self._runtime.settings,
            )
            evidence_issues = reviewer.run_evidence_review(
                presentation_id,
                slides,
                context_bundle=state.get("context_bundle"),
            )
            next_state = cast(
                PresentationWorkflowState,
                {
                    **self._merge_review_findings(state, evidence_issues, reviewer),
                    "current_step": WorkflowStep.EVIDENCE_REVIEW.value,
                },
            )
            merged = cast(PresentationWorkflowState, {**state, **next_state})
            self._persist_checkpoint(merged)
            logger.info("Evidence review recorded %d issue(s)", len(evidence_issues))
            return next_state
        except Exception as exc:
            logger.exception("Evidence review failed: %s", exc)
            return {
                "errors": [str(exc)],
                "current_step": WorkflowStep.EVIDENCE_REVIEW.value,
            }

    def run_architectural_review(self, state: PresentationWorkflowState) -> PresentationWorkflowState:
        logger = self._logger(state)
        if state.get("errors"):
            return {"current_step": WorkflowStep.ARCHITECTURAL_REVIEW.value}

        slides = self._load_slides_for_export(state)
        if not slides:
            return {"current_step": WorkflowStep.ARCHITECTURAL_REVIEW.value}

        try:
            presentation_id = UUID(state["presentation_id"])
            reviewer = AutomatedReviewService(
                self._runtime.session,
                llm=self._runtime.llm,
                settings=self._runtime.settings,
            )
            architectural_issues = reviewer.run_architectural_review(
                presentation_id,
                slides,
                brief=state.get("brief"),
                storyline=state.get("storyline"),
            )
            next_state = cast(
                PresentationWorkflowState,
                {
                    **self._merge_review_findings(state, architectural_issues, reviewer),
                    "current_step": WorkflowStep.ARCHITECTURAL_REVIEW.value,
                },
            )
            merged = cast(PresentationWorkflowState, {**state, **next_state})
            self._persist_checkpoint(merged)
            logger.info("Architectural review recorded %d issue(s)", len(architectural_issues))
            return next_state
        except Exception as exc:
            logger.exception("Architectural review failed: %s", exc)
            return {
                "errors": [str(exc)],
                "current_step": WorkflowStep.ARCHITECTURAL_REVIEW.value,
            }

    def run_layout_review(self, state: PresentationWorkflowState) -> PresentationWorkflowState:
        logger = self._logger(state)
        if state.get("errors"):
            return {"current_step": WorkflowStep.LAYOUT_REVIEW.value}

        slides = self._load_slides_for_export(state)
        if not slides:
            return {"current_step": WorkflowStep.LAYOUT_REVIEW.value}

        try:
            presentation_id = UUID(state["presentation_id"])
            project_id = UUID(state["project_id"]) if state.get("project_id") else None
            reviewer = AutomatedReviewService(
                self._runtime.session,
                llm=self._runtime.llm,
                settings=self._runtime.settings,
            )
            layout_issues = reviewer.run_layout_review(
                presentation_id,
                slides,
                project_id=project_id,
                brief=state.get("brief"),
                storyline=state.get("storyline"),
                context_bundle=state.get("context_bundle"),
            )
            next_state = cast(
                PresentationWorkflowState,
                {
                    **self._merge_review_findings(state, layout_issues, reviewer),
                    "current_step": WorkflowStep.LAYOUT_REVIEW.value,
                },
            )
            merged = cast(PresentationWorkflowState, {**state, **next_state})
            self._persist_checkpoint(merged)
            logger.info("Layout review recorded %d issue(s)", len(layout_issues))
            return next_state
        except Exception as exc:
            logger.exception("Layout review failed: %s", exc)
            return {
                "errors": [str(exc)],
                "current_step": WorkflowStep.LAYOUT_REVIEW.value,
            }

    def run_professional_review(self, state: PresentationWorkflowState) -> PresentationWorkflowState:
        """Backward-compatible alias: runs architectural review only."""
        return self.run_architectural_review(state)

    def repair_slides(self, state: PresentationWorkflowState) -> PresentationWorkflowState:
        logger = self._logger(state)
        if state.get("errors"):
            return {"current_step": WorkflowStep.REPAIR_SLIDES.value}

        slides = self._load_slides_for_export(state)
        if not slides:
            return {"current_step": WorkflowStep.REPAIR_SLIDES.value}

        try:
            presentation_id = UUID(state["presentation_id"])
            repairer = SlideRepairService(
                self._runtime.session,
                llm=self._runtime.llm,
                settings=self._runtime.settings,
            )
            repaired_slides, repair_count = repairer.repair_slides(
                presentation_id,
                slides,
                list(state.get("review_issues", [])),
                brief=state.get("brief"),
            )
            next_state: PresentationWorkflowState = {
                "slides": repaired_slides,
                "repaired_slide_count": repair_count,
                "repair_round": state.get("repair_round", 0) + 1,
                "review_issues": [],
                "slide_review_issues": [],
                "current_step": WorkflowStep.REPAIR_SLIDES.value,
            }
            merged = cast(PresentationWorkflowState, {**state, **next_state})
            self._persist_checkpoint(merged)
            logger.info("Slide repair updated %d slide(s)", repair_count)
            return next_state
        except Exception as exc:
            logger.exception("Slide repair failed: %s", exc)
            return {
                "errors": [str(exc)],
                "current_step": WorkflowStep.REPAIR_SLIDES.value,
            }

    def review_slides(self, state: PresentationWorkflowState) -> PresentationWorkflowState:
        """Summarize automated review findings before export or human review."""
        logger = self._logger(state)
        if state.get("errors"):
            return {"current_step": WorkflowStep.SLIDE_VALIDATION.value}

        slides = self._load_slides_for_export(state)
        if not slides:
            return {
                "errors": ["Cannot review slides without a slide plan"],
                "current_step": WorkflowStep.SLIDE_VALIDATION.value,
            }

        review_issues = list(state.get("review_issues", []))
        slide_review_issues = list(state.get("slide_review_issues", []))
        if not slide_review_issues and review_issues:
            slide_review_issues = AutomatedReviewService(
                self._runtime.session,
                llm=self._runtime.llm,
                settings=self._runtime.settings,
            ).summarize_for_slides(review_issues)

        block_errors = critical_export_block_messages(
            review_issues,
            block_enabled=self._runtime.settings.block_export_on_critical_review,
        )
        if block_errors:
            logger.error("Export blocked by %d critical review issue(s)", len(block_errors))
            return {
                "errors": block_errors,
                "slide_review_issues": slide_review_issues,
                "current_step": WorkflowStep.SLIDE_VALIDATION.value,
            }

        next_state: PresentationWorkflowState = {
            "slide_review_issues": slide_review_issues,
            "current_step": WorkflowStep.SLIDE_VALIDATION.value,
        }
        merged = cast(PresentationWorkflowState, {**state, **next_state})
        self._persist_checkpoint(merged)
        if slide_review_issues:
            logger.warning("Slide validation summary: %d issue(s)", len(slide_review_issues))
        else:
            logger.info("Slide validation passed for %d slides", len(slides))
        return next_state

    def _load_slides_for_export(self, state: PresentationWorkflowState) -> list[SlideSpec]:
        presentation_id = UUID(state["presentation_id"])
        return self._presentations.list_slides(presentation_id)

    def export_json(self, state: PresentationWorkflowState) -> PresentationWorkflowState:
        logger = self._logger(state)
        if state.get("errors"):
            return {"current_step": WorkflowStep.EXPORT.value}
        if not state.get("export_json", True):
            return {"current_step": WorkflowStep.EXPORT.value}

        brief = state.get("brief")
        storyline = state.get("storyline")
        slides = self._load_slides_for_export(state)
        if brief is None or storyline is None:
            return {
                "errors": ["Cannot export JSON without brief and storyline"],
                "current_step": WorkflowStep.EXPORT.value,
            }

        try:
            presentation_id = UUID(state["presentation_id"])
            json_path = self._runtime.json_renderer.render(
                presentation_id=presentation_id,
                brief=brief,
                storyline=storyline,
                slides=slides,
                version=brief.version,
            )
            next_state: PresentationWorkflowState = {
                "json_path": str(json_path),
                "current_step": WorkflowStep.EXPORT.value,
            }
            merged = cast(PresentationWorkflowState, {**state, **next_state})
            self._persist_checkpoint(merged)
            logger.info("Exported presentation JSON to %s", json_path)
            return next_state
        except Exception as exc:
            logger.exception("JSON export failed: %s", exc)
            return {
                "errors": [str(exc)],
                "current_step": WorkflowStep.EXPORT.value,
            }

    def export_presentation_spec(self, state: PresentationWorkflowState) -> PresentationWorkflowState:
        logger = self._logger(state)
        if state.get("errors"):
            return {"current_step": WorkflowStep.PRESENTATION_SPEC.value}
        if not state.get("export_presentation_spec", False):
            return {"current_step": WorkflowStep.PRESENTATION_SPEC.value}

        brief = state.get("brief")
        storyline = state.get("storyline")
        slides = self._load_slides_for_export(state)
        if brief is None or storyline is None:
            return {
                "errors": ["Cannot export PresentationSpec without brief and storyline"],
                "current_step": WorkflowStep.PRESENTATION_SPEC.value,
            }

        try:
            presentation_id = UUID(state["presentation_id"])
            project_id = UUID(state["project_id"])
            spec_path = self._runtime.pptxgen_renderer.render(
                presentation_id=presentation_id,
                project_id=project_id,
                brief=brief,
                storyline=storyline,
                slides=slides,
                version=brief.version,
            )
            next_state: PresentationWorkflowState = {
                "spec_path": str(spec_path),
                "current_step": WorkflowStep.PRESENTATION_SPEC.value,
            }
            if state.get("export_editable_pptx", False):
                extras = export_pptxgen_extras(
                    self._runtime.pptxgen_renderer,
                    spec_path,
                    export_editable_pptx=True,
                )
                if extras.editable_pptx_path is not None:
                    next_state["editable_pptx_path"] = str(extras.editable_pptx_path)
                if extras.warnings:
                    next_state["render_warnings"] = extras.warnings

            merged = cast(PresentationWorkflowState, {**state, **next_state})
            self._persist_checkpoint(merged)
            logger.info("Exported PresentationSpec to %s", spec_path)
            return next_state
        except Exception as exc:
            logger.exception("PresentationSpec export failed: %s", exc)
            return {
                "errors": [str(exc)],
                "current_step": WorkflowStep.PRESENTATION_SPEC.value,
            }

    def export_marp(self, state: PresentationWorkflowState) -> PresentationWorkflowState:
        logger = self._logger(state)
        if state.get("errors"):
            return {"current_step": WorkflowStep.MARP.value}
        if not state.get("export_marp", False):
            return {"current_step": WorkflowStep.MARP.value}

        brief = state.get("brief")
        storyline = state.get("storyline")
        slides = self._load_slides_for_export(state)
        if brief is None or storyline is None:
            return {
                "errors": ["Cannot export Marp without brief and storyline"],
                "current_step": WorkflowStep.MARP.value,
            }

        try:
            presentation_id = UUID(state["presentation_id"])
            marp_md_path = self._runtime.marp_renderer.render(
                presentation_id=presentation_id,
                brief=brief,
                storyline=storyline,
                slides=slides,
                version=brief.version,
            )
            next_state: PresentationWorkflowState = {
                "marp_md_path": str(marp_md_path),
                "current_step": WorkflowStep.MARP.value,
            }
            export_pptx = bool(state.get("export_pptx", False))
            export_pdf = bool(state.get("export_pdf", False))
            export_preview_images = bool(state.get("export_preview_images", False))
            if export_pptx or export_pdf or export_preview_images:
                extras = export_marp_extras(
                    self._runtime.marp_renderer,
                    marp_md_path,
                    export_pptx=export_pptx,
                    export_pdf=export_pdf,
                    export_preview_images=export_preview_images,
                )
                if extras.pptx_path is not None:
                    next_state["marp_pptx_path"] = str(extras.pptx_path)
                if extras.pdf_path is not None:
                    next_state["pdf_path"] = str(extras.pdf_path)
                if extras.preview_images:
                    next_state["preview_image_paths"] = [
                        str(path) for path in extras.preview_images
                    ]
                if extras.warnings:
                    next_state["render_warnings"] = extras.warnings

            merged = cast(PresentationWorkflowState, {**state, **next_state})
            self._persist_checkpoint(merged)
            logger.info("Exported Marp presentation to %s", marp_md_path)
            return next_state
        except Exception as exc:
            logger.exception("Marp export failed: %s", exc)
            return {
                "errors": [str(exc)],
                "current_step": WorkflowStep.MARP.value,
            }

    def _refresh_review_artifacts(
        self,
        state: PresentationWorkflowState,
        gate: str,
    ) -> PresentationWorkflowState:
        presentation_id = UUID(state["presentation_id"])
        updates: PresentationWorkflowState = {}

        brief = state.get("brief")
        if brief is not None:
            refreshed_brief = self._presentations.get_brief(brief.id)
            if refreshed_brief is not None:
                updates["brief"] = refreshed_brief

        if gate in {"storyline", "slides"}:
            storyline = state.get("storyline")
            if storyline is not None:
                refreshed_storyline = self._presentations.get_storyline(storyline.id)
                if refreshed_storyline is not None:
                    updates["storyline"] = refreshed_storyline

        if gate == "slides":
            updates["slides"] = self._presentations.list_slides(presentation_id)

        return updates

    def _gate_ready_to_continue(self, state: PresentationWorkflowState, gate: str) -> bool:
        if gate == "brief":
            brief = state.get("brief")
            if brief is None:
                return False
            refreshed = self._presentations.get_brief(brief.id)
            return refreshed is not None and refreshed.approval_status == ApprovalStatus.APPROVED
        if gate == "storyline":
            storyline = state.get("storyline")
            if storyline is None:
                return False
            refreshed_storyline = self._presentations.get_storyline(storyline.id)
            return (
                refreshed_storyline is not None
                and refreshed_storyline.approval_status == ApprovalStatus.APPROVED
            )
        if gate == "slides":
            slides = self._presentations.list_slides(UUID(state["presentation_id"]))
            return bool(slides) and slides_are_approved(slides)
        return False

    def pause_for_review(self, state: PresentationWorkflowState) -> PresentationWorkflowState:
        logger = self._logger(state)
        review_steps = {
            WorkflowStep.REVIEW_BRIEF.value,
            WorkflowStep.REVIEW_STORYLINE.value,
            WorkflowStep.REVIEW_SLIDES.value,
        }

        workflow_run_id = state.get("workflow_run_id")
        if workflow_run_id is not None:
            run = self._runtime.workflow_runs.get_by_id(UUID(workflow_run_id))
            if run is not None:
                existing_gate = run.state.get("review_gate")
                existing_step = run.state.get("current_step")
                if (
                    isinstance(existing_gate, str)
                    and existing_gate in {"brief", "storyline", "slides"}
                    and isinstance(existing_step, str)
                    and existing_step in review_steps
                    and self._gate_ready_to_continue(state, existing_gate)
                ):
                    refreshed = self._refresh_review_artifacts(state, existing_gate)
                    resume_state: PresentationWorkflowState = {
                        "review_gate": existing_gate,
                        "current_step": existing_step,
                        **refreshed,
                    }
                    resume_merged = cast(PresentationWorkflowState, {**state, **resume_state})
                    self._persist_checkpoint(resume_merged, status=WorkflowStatus.RUNNING)
                    logger.info("Workflow resumed after %s review", existing_gate)
                    return resume_state

        brief = state.get("brief")
        storyline = state.get("storyline")
        slides = self._load_slides_for_export(state)

        if brief is not None and brief.approval_status != ApprovalStatus.APPROVED:
            gate = "brief"
            step = WorkflowStep.REVIEW_BRIEF.value
        elif storyline is not None and storyline.approval_status != ApprovalStatus.APPROVED:
            gate = "storyline"
            step = WorkflowStep.REVIEW_STORYLINE.value
        elif slides and state.get("require_slides_review") and not slides_are_approved(slides):
            gate = "slides"
            step = WorkflowStep.REVIEW_SLIDES.value
        else:
            return {"current_step": WorkflowStep.FINALIZE.value}

        next_state: PresentationWorkflowState = {
            "current_step": step,
            "review_gate": gate,
        }
        merged = cast(PresentationWorkflowState, {**state, **next_state})
        self._persist_checkpoint(merged, status=WorkflowStatus.AWAITING_REVIEW)
        logger.info("Workflow paused for %s review on presentation %s", gate, state.get("presentation_id"))

        interrupt({"gate": gate, "step": step})

        refreshed = self._refresh_review_artifacts(merged, gate)
        resume_state = {
            **next_state,
            **refreshed,
        }
        resume_merged = cast(PresentationWorkflowState, {**merged, **resume_state})
        self._persist_checkpoint(resume_merged, status=WorkflowStatus.RUNNING)
        logger.info("Workflow resumed after %s review", gate)
        return resume_state

    def finalize(self, state: PresentationWorkflowState) -> PresentationWorkflowState:
        logger = self._logger(state)
        presentation = state.get("presentation")
        brief = state.get("brief")
        storyline = state.get("storyline")
        errors = list(state.get("errors", []))

        if presentation is not None and not errors:
            presentation.current_brief_id = brief.id if brief else None
            presentation.current_storyline_id = storyline.id if storyline else None
            awaiting_review = self._pending_human_review(state)
            has_exports = bool(state.get("json_path") or state.get("marp_md_path"))

            if awaiting_review:
                presentation.status = PresentationStatus.IN_PROGRESS
                status = WorkflowStatus.AWAITING_REVIEW
                step = WorkflowStep.FINALIZE.value
            elif has_exports:
                presentation.status = PresentationStatus.EXPORTED
                status = WorkflowStatus.COMPLETED
                step = WorkflowStep.FINALIZE.value
            else:
                presentation.status = PresentationStatus.REVIEW
                status = WorkflowStatus.COMPLETED
                step = WorkflowStep.FINALIZE.value

            presentation = self._presentations.update_presentation(presentation)
        else:
            status = WorkflowStatus.FAILED
            step = WorkflowStep.FAILED.value

        next_state: PresentationWorkflowState = {
            "presentation": presentation,
            "current_step": step,
        }
        merged = cast(PresentationWorkflowState, {**state, **next_state})
        self._persist_checkpoint(merged, status=status)
        if errors:
            logger.error("Workflow failed with %d error(s)", len(errors))
        else:
            logger.info("Workflow completed for presentation %s", state.get("presentation_id"))
        return next_state

    def _pending_human_review(self, state: PresentationWorkflowState) -> bool:
        if state.get("require_brief_review"):
            brief = state.get("brief")
            if brief is not None:
                refreshed = self._presentations.get_brief(brief.id)
                if refreshed is not None and refreshed.approval_status != ApprovalStatus.APPROVED:
                    return True

        if state.get("require_storyline_review"):
            storyline = state.get("storyline")
            if storyline is not None:
                refreshed_storyline = self._presentations.get_storyline(storyline.id)
                if (
                    refreshed_storyline is not None
                    and refreshed_storyline.approval_status != ApprovalStatus.APPROVED
                ):
                    return True

        if state.get("require_slides_review"):
            slides = self._load_slides_for_export(state)
            if slides and not slides_are_approved(slides):
                return True

        return False
