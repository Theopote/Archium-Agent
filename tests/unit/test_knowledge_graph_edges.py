"""Phase C — confirmed knowledge-graph edges persist across rebuilds."""

from __future__ import annotations

from archium.application.knowledge_graph_service import KnowledgeGraphService
from archium.application.project_knowledge_service import ProjectKnowledgeService
from archium.domain.design_knowledge import DesignKnowledge
from archium.domain.enums import (
    InformationOrigin,
    InformationReliability,
    ProjectOriginMode,
)
from archium.domain.knowledge_graph import KnowledgeRelationKind
from archium.domain.project import Project
from archium.infrastructure.database.repositories import (
    KnowledgeGraphEdgeRepository,
    ProjectRepository,
)


def test_confirm_edge_survives_snapshot_rebuild(db_session) -> None:
    project = ProjectRepository(db_session).create(
        Project(name="图边持久化", origin_mode=ProjectOriginMode.CONCEPT_EXPLORATION)
    )
    graph = KnowledgeGraphService(db_session)
    edge = graph.confirm_edge(
        project.id,
        relation=KnowledgeRelationKind.SIMILAR_TO,
        source_ref="case:ningbo_museum",
        target_ref="case:therme_vals",
        evidence="用户确认：在地材料与嵌入策略可并置讨论",
    )
    db_session.commit()
    assert edge.status.value == "active"

    # Fresh service instance = new "process"
    rebuilt = KnowledgeGraphService(db_session).build_snapshot(project.id)
    confirmed = [e for e in rebuilt.edges if e.confirmed]
    assert any(
        e.source_id == "case:ningbo_museum"
        and e.target_id == "case:therme_vals"
        and e.relation == KnowledgeRelationKind.SIMILAR_TO
        for e in confirmed
    )
    neighbors = rebuilt.neighbors("case:ningbo_museum")
    assert any(node.id == "case:therme_vals" for _, node in neighbors)


def test_research_confirm_writes_inspired_by_edge(db_session) -> None:
    project = ProjectRepository(db_session).create(
        Project(name="确认写边", origin_mode=ProjectOriginMode.CONCEPT_EXPLORATION)
    )
    knowledge_svc = ProjectKnowledgeService(db_session)
    item = knowledge_svc.create_item(
        project.id,
        statement="王澍在地材料",
        origin=InformationOrigin.PUBLIC_RESEARCH,
        reliability=InformationReliability.UNVERIFIED,
        category="research",
        requires_user_confirmation=True,
        design_knowledge=DesignKnowledge(
            topic="在地材料",
            problem="地方记忆容器",
            strategy="瓦爿墙",
            principle="材料回收承载叙事",
            precedent_ref="case:ningbo_museum",
        ),
    )
    db_session.commit()
    confirmed = knowledge_svc.confirm_item(item.id)
    db_session.commit()

    edges = KnowledgeGraphEdgeRepository(db_session).list_by_project(project.id)
    assert len(edges) >= 1
    assert any(
        e.relation == KnowledgeRelationKind.INSPIRED_BY
        and e.target_ref == "case:ningbo_museum"
        and e.source_ref == f"knowledge:{confirmed.id}"
        for e in edges
    )

    snapshot = KnowledgeGraphService(db_session).build_snapshot(project.id)
    assert any(
        e.confirmed
        and e.relation == KnowledgeRelationKind.INSPIRED_BY
        and e.target_id == "case:ningbo_museum"
        for e in snapshot.edges
    )


def test_revoke_edge_removes_from_active_snapshot(db_session) -> None:
    project = ProjectRepository(db_session).create(
        Project(name="撤销边", origin_mode=ProjectOriginMode.CONCEPT_EXPLORATION)
    )
    graph = KnowledgeGraphService(db_session)
    edge = graph.confirm_edge(
        project.id,
        relation=KnowledgeRelationKind.SIMILAR_TO,
        source_ref="concept:courtyard",
        target_ref="case:salk_institute",
    )
    db_session.commit()
    graph.revoke_edge(edge.id)
    db_session.commit()

    snapshot = KnowledgeGraphService(db_session).build_snapshot(project.id)
    assert not any(
        e.confirmed
        and e.source_id == "concept:courtyard"
        and e.target_id == "case:salk_institute"
        for e in snapshot.edges
    )
    active = KnowledgeGraphEdgeRepository(db_session).list_by_project(
        project.id, active_only=True
    )
    assert active == []
