"""Rebuild ProjectContext from persisted project state (no LLM)."""

from __future__ import annotations

import contextlib
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.context.knowledge_claim_index import merge_claim_index_into_state
from archium.application.context.next_action_selector import default_actions_for_stage
from archium.application.context.project_context_composer import compose_project_context
from archium.application.context.types import ContextAssessment
from archium.application.context_evidence import ProjectEvidencePack, gather_project_evidence
from archium.domain.context.legacy_origin import apply_legacy_origin
from archium.domain.context.project_context import ProjectContext
from archium.domain.project import Project


def build_project_context(
    session: Session,
    project: Project | UUID,
) -> ProjectContext | None:
    """Reconstruct ProjectContext from knowledge_state and current evidence.

    Refreshes the claim index deterministically (no LLM) so Fact / KnowledgeItem
    changes appear even before the next full reassess.
    """
    from archium.infrastructure.database.repositories import ProjectRepository

    if isinstance(project, UUID):
        loaded = ProjectRepository(session).get_by_id(project)
        if loaded is None:
            return None
        project = loaded
    if project.knowledge_state is None:
        return None
    evidence = gather_project_evidence(session, project.id)
    knowledge_state = merge_claim_index_into_state(project.knowledge_state, evidence)
    actions = default_actions_for_stage(
        knowledge_state.maturity_stage.value,
        has_materials=evidence.has_evidence,
        blocking_gaps=evidence.blocking_gap_count > 0,
    )
    assessment = ContextAssessment(
        knowledge_state=knowledge_state,
        actions=actions,
        suggested_origin_mode=project.origin_mode,
    )
    ctx = compose_project_context(
        assessment,
        evidence=evidence,
        user_text=(project.description or project.name or "").strip(),
    )
    ctx = overlay_persisted_routing(ctx, project.knowledge_state)
    return apply_legacy_origin(ctx)

def overlay_persisted_routing(ctx: ProjectContext, knowledge_state: Any) -> ProjectContext:
    """Prefer routing snapshot persisted at last assessment."""
    from archium.domain.context.lifecycle_stage import ProjectLifecycleStage
    from archium.domain.context.recommended_workflow import RecommendedWorkflow

    updates: dict[str, object] = {}
    stage_raw = (knowledge_state.lifecycle_stage or "").strip()
    if stage_raw:
        with contextlib.suppress(ValueError):
            updates["lifecycle_stage"] = ProjectLifecycleStage(stage_raw)
    workflow_raw = (knowledge_state.recommended_workflow or "").strip()
    if workflow_raw:
        with contextlib.suppress(ValueError):
            updates["recommended_workflow"] = RecommendedWorkflow(workflow_raw)
    if knowledge_state.primary_page_key:
        updates["primary_page_key"] = knowledge_state.primary_page_key
    if not updates:
        return ctx
    return ctx.model_copy(update=updates)

def input_sources_from_evidence(evidence: ProjectEvidencePack) -> list[str]:
    sources: list[str] = []
    if evidence.document_count:
        sources.append(f"documents:{evidence.document_count}")
    if evidence.confirmed_fact_count:
        sources.append(f"confirmed_facts:{evidence.confirmed_fact_count}")
    if evidence.extracted_fact_count:
        sources.append(f"extracted_facts:{evidence.extracted_fact_count}")
    if evidence.knowledge_item_count:
        sources.append(f"knowledge_items:{evidence.knowledge_item_count}")
    if evidence.chunk_excerpts.strip():
        sources.append("document_excerpts")
    sources.extend(list(getattr(evidence, "visual_input_sources", ()) or ()))
    return sources
