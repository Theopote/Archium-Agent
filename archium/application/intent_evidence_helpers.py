"""Helpers to build IntentEvidence from research / direction / user edits."""

from __future__ import annotations

from archium.domain.concept_direction import ConceptDirection
from archium.domain.intent.intent_evidence import IntentEvidence, IntentEvidenceSourceType
from archium.domain.project_knowledge import ProjectKnowledgeItem


def evidence_from_research_item(item: ProjectKnowledgeItem) -> IntentEvidence:
    summary = item.statement.strip().split("\n\n")[0].strip()
    materials: list[str] = []
    for citation in item.source_citations[:3]:
        if getattr(citation, "url", None):
            materials.append(str(citation.url))
        elif getattr(citation, "source_title", None):
            materials.append(str(citation.source_title))
        elif getattr(citation, "document_name", None):
            name = str(citation.document_name).strip()
            if name:
                materials.append(name)
    return IntentEvidence(
        statement=summary[:800],
        source_type=IntentEvidenceSourceType.PUBLIC_RESEARCH,
        confidence=0.55,
        created_by="research",
        field_hint="project_context",
        supporting_materials=materials,
        note="已确认公开研究写回 Mission",
    )


def evidence_from_direction_selection(direction: ConceptDirection) -> IntentEvidence:
    title = direction.title.strip() or "未命名方向"
    theme = (direction.theme or direction.summary or "").strip()
    statement = f"选定方向「{title}」"
    if theme:
        statement = f"{statement}：{theme}"
    return IntentEvidence(
        statement=statement[:800],
        source_type=IntentEvidenceSourceType.DIRECTION_SELECTION,
        confidence=0.72,
        created_by="exploration",
        field_hint="theme",
        supporting_materials=[title],
        note="概念方向选定写入 DesignIntent",
    )


def evidence_from_user_assumption(statement: str) -> IntentEvidence | None:
    text = statement.strip()
    if not text:
        return None
    return IntentEvidence(
        statement=text[:800],
        source_type=IntentEvidenceSourceType.ARCHITECT_ASSUMPTION,
        confidence=0.4,
        created_by="user",
        field_hint="working_assumptions",
        note="工作假设（待确认）",
    )
