"""Ingestion workflow nodes — project load, sources, facts."""

from __future__ import annotations

from typing import cast
from uuid import UUID

from archium.agents._helpers import build_project_context_bundle, build_retrieval_query_from_request
from archium.application.fact_extraction_service import FactExtractionService
from archium.application.fact_validation_service import FactValidationService
from archium.domain.enums import WorkflowStep
from archium.infrastructure.database.repositories import (
    DocumentRepository,
    FactRepository,
    ProjectRepository,
)
from archium.workflow.nodes.base import WorkflowNodeBase
from archium.workflow.state import PresentationWorkflowState


class IngestionNodesMixin(WorkflowNodeBase):
    """Load project context and validate upstream sources."""

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
