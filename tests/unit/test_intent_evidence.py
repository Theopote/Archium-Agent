"""Unit tests for IntentEvidence provenance on DesignIntent."""

from __future__ import annotations

from archium.application.intent_evidence_helpers import (
    evidence_from_direction_selection,
    evidence_from_research_item,
)
from archium.domain.concept_direction import ConceptDirection
from archium.domain.enums import InformationOrigin, InformationReliability
from archium.domain.intent.design_intent import DesignIntent
from archium.domain.intent.intent_evidence import (
    IntentEvidence,
    IntentEvidenceSourceType,
)
from archium.domain.project_knowledge import ProjectKnowledgeItem, SourceCitation


def test_design_intent_with_evidence_dedupes() -> None:
    first = IntentEvidence(
        statement="庭院回应关中聚落",
        source_type=IntentEvidenceSourceType.PUBLIC_RESEARCH,
        confidence=0.5,
    )
    intent = DesignIntent(theme="地域再生").with_evidence(first, first)
    assert len(intent.evidence) == 1
    block = intent.to_prompt_block()
    assert "意图出处" in block
    assert "公开研究" in block


def test_evidence_from_research_item_uses_citations() -> None:
    item = ProjectKnowledgeItem(
        project_id=__import__("uuid").uuid4(),
        statement="关中乡村公共文化空间常结合集市与祠堂。\n\n要点：\n- 复合功能",
        origin=InformationOrigin.PUBLIC_RESEARCH,
        reliability=InformationReliability.UNVERIFIED,
        source_citations=[
            SourceCitation(
                url="https://example.org/loess",
                source_title="关中研究",
                document_name="web",
            )
        ],
    )
    evidence = evidence_from_research_item(item)
    assert evidence.source_type == IntentEvidenceSourceType.PUBLIC_RESEARCH
    assert "关中" in evidence.statement
    assert "要点" not in evidence.statement
    assert any("example.org" in m for m in evidence.supporting_materials)


def test_evidence_from_direction_selection() -> None:
    direction = ConceptDirection(
        project_id=__import__("uuid").uuid4(),
        title="日常文化庭院",
        theme="青年日常",
        summary="以庭院组织日常文化活动",
    )
    evidence = evidence_from_direction_selection(direction)
    assert evidence.source_type == IntentEvidenceSourceType.DIRECTION_SELECTION
    assert "日常文化庭院" in evidence.statement


def test_enrich_mission_writes_intent_evidence(db_session) -> None:
    from archium.application.mission_research_enrichment_service import (
        MissionResearchEnrichmentService,
    )
    from archium.application.project_knowledge_service import ProjectKnowledgeService
    from archium.domain.enums import ProjectOriginMode
    from archium.domain.project import Project
    from archium.domain.project_mission import ProjectMission
    from archium.infrastructure.database.mission_repositories import MissionRepository
    from archium.infrastructure.database.repositories import ProjectRepository

    project = ProjectRepository(db_session).create(
        Project(name="研究写回出处", origin_mode=ProjectOriginMode.CONCEPT_EXPLORATION)
    )
    mission = MissionRepository(db_session).save_mission(
        ProjectMission(
            project_id=project.id,
            title="概念探索",
            task_statement="探索黄土高原文化中心",
            project_context="初始语境",
        )
    )
    knowledge = ProjectKnowledgeService(db_session)
    item = knowledge.create_item(
        project.id,
        statement="关中乡村公共文化空间常结合集市与祠堂功能。",
        origin=InformationOrigin.PUBLIC_RESEARCH,
        reliability=InformationReliability.UNVERIFIED,
        requires_user_confirmation=True,
        category="research",
    )
    knowledge.confirm_item(item.id)

    result = MissionResearchEnrichmentService(db_session, llm=None).enrich_mission(
        mission.id, prefer_llm=False
    )
    intent = result.mission.design_intent
    assert intent is not None
    assert intent.evidence
    assert intent.evidence[0].source_type == IntentEvidenceSourceType.PUBLIC_RESEARCH
    assert "关中" in intent.evidence[0].statement

    from archium.infrastructure.database.repositories import ProjectRepository

    project = ProjectRepository(db_session).get_by_id(result.mission.project_id)
    assert project is not None
    research_events = [
        e for e in project.intent_evolution.events if e.kind.value == "research"
    ]
    assert research_events
    assert research_events[-1].design_intent_snapshot
    assert research_events[-1].design_intent_snapshot.get("evidence")
