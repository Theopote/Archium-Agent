"""Load DesignKnowledge blocks for Concept / Critique prompts."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.domain.design_knowledge import DesignKnowledge
from archium.domain.enums import InformationOrigin, KnowledgeItemStatus
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
) -> str:
    """Prompt section for concept / critique injection."""
    entries = list_design_knowledge_for_project(session, project_id, limit=limit)
    if not entries:
        return ""
    parts = ["【已沉淀设计知识 DesignKnowledge】（优先转译空间策略，勿当装饰文案）"]
    for index, knowledge in enumerate(entries, start=1):
        block = knowledge.to_prompt_block()
        if block.strip():
            parts.append(f"[{index}]\n{block}")
    return "\n\n".join(parts)


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
                knowledge.principle or knowledge.insight,
                knowledge.spatial_translation,
            )
            if part and str(part).strip()
        )
        if compact.strip():
            lines.append(compact.strip()[:400])
    return lines
