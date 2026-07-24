"""Helpers to build IntentEvidence from research / direction / user edits."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.domain.concept_direction import ConceptDirection
from archium.domain.fact import ProjectFact
from archium.domain.intent.design_intent import DesignIntent
from archium.domain.intent.intent_evidence import IntentEvidence, IntentEvidenceSourceType
from archium.domain.intent.intent_evolution import IntentEvolution, IntentEvolutionKind
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


def evidence_from_confirmed_fact(fact: ProjectFact) -> IntentEvidence:
    unit = f" {fact.unit}" if fact.unit else ""
    statement = f"{fact.label}: {fact.value}{unit}"
    materials: list[str] = []
    for citation in fact.source_citations[:3]:
        name = getattr(citation, "document_name", None) or ""
        if str(name).strip():
            page = getattr(citation, "page_number", None)
            label = str(name).strip()
            if page:
                label = f"{label} p.{page}"
            materials.append(label)
    return IntentEvidence(
        statement=statement[:800],
        source_type=IntentEvidenceSourceType.DOCUMENT,
        confidence=max(0.6, min(1.0, float(fact.confidence or 0.8))),
        created_by="user",
        field_hint=fact.key,
        supporting_materials=materials,
        note="用户确认项目事实",
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


def record_intent_evidence(
    session: Session,
    project_id: UUID,
    *items: IntentEvidence,
    summary: str,
    kind: IntentEvolutionKind = IntentEvolutionKind.EVIDENCE,
    write_to_mission: bool = True,
) -> list[IntentEvidence]:
    """Append IntentEvolution and optionally merge evidence into latest Mission DesignIntent."""
    from archium.infrastructure.database.mission_repositories import MissionRepository
    from archium.infrastructure.database.repositories import ProjectRepository

    cleaned = [item for item in items if item.statement.strip()]
    if not cleaned:
        return []

    projects = ProjectRepository(session)
    project = projects.get_by_id(project_id)
    if project is None:
        return cleaned

    snapshot = {
        "evidence": [item.model_dump(mode="json") for item in cleaned],
    }
    evo = project.intent_evolution or IntentEvolution()
    project.intent_evolution = evo.append(
        kind,
        summary.strip()[:480] or "意图出处更新",
        design_intent_snapshot=snapshot,
    )
    project.touch()
    projects.update(project)

    if not write_to_mission:
        return cleaned

    missions = MissionRepository(session).list_missions_by_project(project_id)
    if not missions:
        return cleaned
    mission = missions[0]
    intent = mission.design_intent or DesignIntent()
    updated = intent.with_evidence(*cleaned)
    if updated.evidence == intent.evidence:
        return cleaned
    # Provenance-only write: do not invalidate mission approval.
    mission.design_intent = updated
    mission.touch()
    MissionRepository(session).save_mission(mission)
    return cleaned
