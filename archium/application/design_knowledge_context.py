"""Load DesignKnowledge + ArchitectureCase blocks for Concept / Critique prompts."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.architecture_case_library import ArchitectureCaseLibraryService
from archium.domain.design_knowledge import DesignKnowledge
from archium.domain.enums import InformationOrigin, KnowledgeItemStatus
from archium.domain.intent.design_intent import DesignIntent
from archium.domain.research_question import ResearchQuestion
from archium.infrastructure.database.repositories import ProjectKnowledgeRepository


def list_design_knowledge_for_project(
    session: Session,
    project_id: UUID,
    *,
    limit: int = 8,
) -> list[DesignKnowledge]:
    """Active research items that carry structured DesignKnowledge."""
    items = ProjectKnowledgeRepository(session).list_by_project(project_id)
    results: list[DesignKnowledge] = []
    for item in items:
        if item.status in {KnowledgeItemStatus.REJECTED, KnowledgeItemStatus.SUPERSEDED}:
            continue
        if item.origin != InformationOrigin.PUBLIC_RESEARCH:
            continue
        knowledge = item.design_knowledge
        if knowledge is None or not knowledge.has_substance:
            continue
        results.append(knowledge)
        if len(results) >= limit:
            break
    return results


def format_design_knowledge_block(
    session: Session,
    project_id: UUID,
    *,
    limit: int = 6,
    design_intent: DesignIntent | None = None,
    research_questions: list[ResearchQuestion] | None = None,
    query_hint: str = "",
    include_cases: bool = True,
    case_limit: int = 2,
) -> str:
    """Prompt section for concept / critique injection."""
    parts: list[str] = []
    entries = list_design_knowledge_for_project(session, project_id, limit=limit)
    if entries:
        parts.append("【已沉淀设计知识 DesignKnowledge】（优先转译空间策略，勿当装饰文案）")
        for index, knowledge in enumerate(entries, start=1):
            block = knowledge.to_prompt_block()
            if block.strip():
                parts.append(f"[{index}]\n{block}")

    if include_cases:
        case_block = format_architecture_case_block(
            design_intent=design_intent,
            research_questions=research_questions,
            query_hint=query_hint,
            limit=case_limit,
        )
        if case_block.strip():
            parts.append(case_block)

    return "\n\n".join(parts)


def format_architecture_case_block(
    *,
    design_intent: DesignIntent | None = None,
    research_questions: list[ResearchQuestion] | None = None,
    query_hint: str = "",
    limit: int = 2,
) -> str:
    """Semantic case references (cross-type), independent of project DB."""
    library = ArchitectureCaseLibraryService()
    matches = []
    if research_questions:
        matches = library.search_for_questions(research_questions, limit=limit)
    if not matches and design_intent is not None:
        matches = library.search_for_intent(
            design_intent,
            extra_queries=[query_hint] if query_hint.strip() else None,
            limit=limit,
        )
    if not matches and query_hint.strip():
        matches = library.search(query_hint, limit=limit)
    return library.format_prompt_block(matches)


def design_knowledge_summary_lines(
    session: Session,
    project_id: UUID,
    *,
    limit: int = 8,
) -> list[str]:
    """Short lines for critic research_summaries (structured when available)."""
    lines: list[str] = []
    for knowledge in list_design_knowledge_for_project(session, project_id, limit=limit):
        compact = " | ".join(
            part
            for part in (
                knowledge.topic,
                knowledge.problem,
                knowledge.strategy or knowledge.principle or knowledge.insight,
                knowledge.spatial_translation,
            )
            if part and str(part).strip()
        )
        if compact.strip():
            lines.append(compact.strip()[:400])
    return lines
