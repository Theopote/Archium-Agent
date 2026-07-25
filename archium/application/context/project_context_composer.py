"""Compose ProjectContext from assessment outputs."""

from __future__ import annotations

from archium.application.context.knowledge_claim_index import merge_claim_index_into_state
from archium.application.context.next_action_selector import resolve_action_target
from archium.application.context.types import ContextAssessment
from archium.application.context_evidence import ProjectEvidencePack
from archium.domain.context.legacy_origin import apply_legacy_origin
from archium.domain.context.project_context import ProjectContext


def finalize_assessment_context(assessment: ContextAssessment) -> None:
    if assessment.project_context is None:
        return
    assessment.project_context = apply_legacy_origin(assessment.project_context)
    assessment.suggested_origin_mode = assessment.project_context.suggested_origin_mode


def compose_project_context(
    assessment: ContextAssessment,
    *,
    evidence: ProjectEvidencePack | None = None,
    user_text: str = "",
) -> ProjectContext:
    sources: list[str] = []
    if user_text.strip():
        sources.append("user_description")
    pack = evidence or ProjectEvidencePack()
    if pack.document_count:
        sources.append(f"documents:{pack.document_count}")
    if pack.confirmed_fact_count:
        sources.append(f"confirmed_facts:{pack.confirmed_fact_count}")
    if pack.extracted_fact_count:
        sources.append(f"extracted_facts:{pack.extracted_fact_count}")
    if pack.knowledge_item_count:
        sources.append(f"knowledge_items:{pack.knowledge_item_count}")
    if pack.chunk_excerpts.strip():
        sources.append("document_excerpts")
    primary = ""
    if assessment.actions:
        primary = resolve_action_target(
            assessment.actions[0].action,
            pending_fact_count=pack.pending_fact_count,
            conflict_fact_count=pack.conflict_fact_count,
        ).page_key
    return ProjectContext.compose(
        knowledge_state=assessment.knowledge_state,
        next_actions=assessment.actions,
        understanding_summary=assessment.understanding_summary,
        suggested_origin_mode=assessment.suggested_origin_mode,
        input_sources=sources,
        primary_page_key=primary,
    )


def enrich_knowledge_state_counts(
    state,
    evidence: ProjectEvidencePack,
) -> object:
    """Attach evidence counts and claim index to KnowledgeState."""
    return merge_claim_index_into_state(state, evidence)
