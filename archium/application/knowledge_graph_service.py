"""Build & query Architectural Knowledge Graph (Service, not Agent)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from archium.application.architecture_case_library import ArchitectureCaseLibraryService
from archium.application.retrieval_credibility import rank_relevance
from archium.application.retrieval_hybrid import keyword_overlap_score
from archium.application.unit_of_work import SessionLike, session_of
from archium.config.settings import Settings, get_settings
from archium.domain.architecture_case import ArchitectureCase
from archium.domain.enums import KnowledgeItemStatus, VerificationStatus
from archium.domain.knowledge_graph import (
    ConfirmedEdgeSource,
    ConfirmedEdgeStatus,
    ConfirmedKnowledgeEdge,
    KnowledgeEdge,
    KnowledgeGraphSnapshot,
    KnowledgeNode,
    KnowledgeNodeKind,
    KnowledgeRelationKind,
    infer_node_kind_from_ref,
)
from archium.domain.knowledge_reference import (
    KnowledgeReference,
    KnowledgeSourceKind,
    KnowledgeUsage,
)
from archium.domain.project_knowledge import ProjectKnowledgeItem
from archium.exceptions import WorkflowError
from archium.infrastructure.database.repositories import (
    FactRepository,
    KnowledgeGraphEdgeRepository,
    ProjectKnowledgeRepository,
)


class KnowledgeGraphService:
    """Assemble project + seed-case graph and expand retrieval via relations."""

    def __init__(
        self,
        session: SessionLike,
        *,
        settings: Settings | None = None,
        case_library: ArchitectureCaseLibraryService | None = None,
    ) -> None:
        session = session_of(session)
        self._session = session
        self._settings = settings or get_settings()
        self._facts = FactRepository(session)
        self._knowledge = ProjectKnowledgeRepository(session)
        self._confirmed_edges = KnowledgeGraphEdgeRepository(session)
        self._cases = case_library

    def build_snapshot(self, project_id: UUID) -> KnowledgeGraphSnapshot:
        cases = self._cases or ArchitectureCaseLibraryService(
            session=self._session,
            project_id=project_id,
            include_drafts=True,
        )
        nodes: dict[str, KnowledgeNode] = {}
        edges: list[KnowledgeEdge] = []

        def add_node(node: KnowledgeNode) -> None:
            nodes[node.id] = node

        def add_edge(
            *,
            relation: KnowledgeRelationKind,
            source_id: str,
            target_id: str,
            weight: float = 1.0,
            evidence: str = "",
            confirmed: bool = False,
        ) -> None:
            if source_id not in nodes or target_id not in nodes:
                return
            edge_id = f"{source_id}:{relation.value}:{target_id}"
            key = edge_id[:160]
            if confirmed:
                edges[:] = [
                    edge
                    for edge in edges
                    if not (
                        edge.source_id == source_id
                        and edge.target_id == target_id
                        and edge.relation == relation
                    )
                ]
            edges.append(
                KnowledgeEdge(
                    id=key,
                    relation=relation,
                    source_id=source_id,
                    target_id=target_id,
                    weight=weight,
                    evidence=evidence[:300],
                    confirmed=confirmed,
                )
            )

        for fact in self._facts.list_by_project(project_id):
            if fact.verification_status == VerificationStatus.REJECTED:
                continue
            node_id = f"fact:{fact.id}"
            add_node(
                KnowledgeNode(
                    id=node_id,
                    kind=KnowledgeNodeKind.FACT,
                    label=fact.label,
                    summary=f"{fact.value}" + (f" {fact.unit}" if fact.unit else ""),
                    project_id=project_id,
                    source_ref=node_id,
                    tags=[fact.key, fact.category],
                )
            )

        items = [
            item
            for item in self._knowledge.list_by_project(project_id)
            if item.status in {KnowledgeItemStatus.ACTIVE, KnowledgeItemStatus.CONFIRMED}
        ]
        for item in items:
            self._add_knowledge_item_subgraph(item, project_id, add_node, add_edge)

        for case in cases.list_cases():
            self._add_case_subgraph(case, add_node, add_edge)

        self._merge_confirmed_edges(project_id, nodes, add_node, add_edge)

        return KnowledgeGraphSnapshot(
            project_id=project_id,
            nodes=list(nodes.values()),
            edges=edges,
        )

    def confirm_edge(
        self,
        project_id: UUID,
        *,
        relation: KnowledgeRelationKind,
        source_ref: str,
        target_ref: str,
        weight: float = 1.0,
        evidence: str = "",
        source: ConfirmedEdgeSource = ConfirmedEdgeSource.USER,
        knowledge_item_id: UUID | None = None,
    ) -> ConfirmedKnowledgeEdge:
        """Upsert an active confirmed edge (idempotent on endpoints+relation)."""
        source_ref = source_ref.strip()[:120]
        target_ref = target_ref.strip()[:120]
        if not source_ref or not target_ref:
            raise WorkflowError("Confirmed edge requires source_ref and target_ref")
        existing = self._confirmed_edges.get_by_endpoints(
            project_id,
            relation=relation,
            source_ref=source_ref,
            target_ref=target_ref,
        )
        if existing is not None:
            existing.status = ConfirmedEdgeStatus.ACTIVE
            existing.weight = weight
            existing.evidence = evidence[:500]
            existing.source = source
            if knowledge_item_id is not None:
                existing.knowledge_item_id = knowledge_item_id
            existing.touch()
            return self._confirmed_edges.update(existing)
        edge = ConfirmedKnowledgeEdge(
            project_id=project_id,
            relation=relation,
            source_ref=source_ref,
            target_ref=target_ref,
            weight=weight,
            evidence=evidence[:500],
            status=ConfirmedEdgeStatus.ACTIVE,
            source=source,
            knowledge_item_id=knowledge_item_id,
        )
        return self._confirmed_edges.create(edge)

    def revoke_edge(self, edge_id: UUID) -> ConfirmedKnowledgeEdge:
        edge = self._confirmed_edges.get_by_id(edge_id)
        if edge is None:
            raise WorkflowError(f"Knowledge graph edge {edge_id} not found")
        edge.revoke()
        return self._confirmed_edges.update(edge)

    def list_confirmed_edges(
        self, project_id: UUID, *, active_only: bool = True
    ) -> list[ConfirmedKnowledgeEdge]:
        return self._confirmed_edges.list_by_project(
            project_id, active_only=active_only
        )

    def ensure_edges_from_knowledge_item(
        self, item: ProjectKnowledgeItem
    ) -> list[ConfirmedKnowledgeEdge]:
        """Persist durable edges when research knowledge is confirmed (Phase C)."""
        created: list[ConfirmedKnowledgeEdge] = []
        item_ref = f"knowledge:{item.id}"
        dk = item.design_knowledge
        if dk is not None:
            from archium.domain.case_ref import case_id_from_ref, normalize_precedent_ref

            case_id = case_id_from_ref(dk.precedent_ref)
            if case_id:
                created.append(
                    self.confirm_edge(
                        item.project_id,
                        relation=KnowledgeRelationKind.INSPIRED_BY,
                        source_ref=item_ref,
                        target_ref=normalize_precedent_ref(case_id) or f"case:{case_id}",
                        weight=0.95,
                        evidence="precedent_ref",
                        source=ConfirmedEdgeSource.RESEARCH_CONFIRM,
                        knowledge_item_id=item.id,
                    )
                )
        if item.linked_fact_id is not None:
            created.append(
                self.confirm_edge(
                    item.project_id,
                    relation=KnowledgeRelationKind.LINKED_FACT,
                    source_ref=item_ref,
                    target_ref=f"fact:{item.linked_fact_id}",
                    weight=1.0,
                    evidence="linked_fact_id",
                    source=ConfirmedEdgeSource.RESEARCH_CONFIRM,
                    knowledge_item_id=item.id,
                )
            )
        return created

    def _merge_confirmed_edges(
        self,
        project_id: UUID,
        nodes: dict[str, KnowledgeNode],
        add_node: Any,
        add_edge: Any,
    ) -> None:
        for confirmed in self._confirmed_edges.list_by_project(project_id, active_only=True):
            for ref in (confirmed.source_ref, confirmed.target_ref):
                if ref in nodes:
                    continue
                kind = infer_node_kind_from_ref(ref)
                label = ref.split(":", 1)[-1][:300] or ref
                add_node(
                    KnowledgeNode(
                        id=ref,
                        kind=kind,
                        label=label,
                        summary="confirmed-edge stub",
                        project_id=project_id,
                        source_ref=ref,
                        tags=["confirmed_stub"],
                        extra={"stub": True},
                    )
                )
            add_edge(
                relation=confirmed.relation,
                source_id=confirmed.source_ref,
                target_id=confirmed.target_ref,
                weight=confirmed.weight,
                evidence=confirmed.evidence or "confirmed",
                confirmed=True,
            )

    def retrieve_via_graph(
        self,
        project_id: UUID,
        query: str,
        *,
        top_k: int = 8,
        hops: int = 1,
    ) -> list[KnowledgeReference]:
        """Match query → seed nodes → expand relations → KnowledgeReference hits."""
        query = (query or "").strip()
        if not query:
            return []
        snapshot = self.build_snapshot(project_id)
        seeds = snapshot.match_nodes(query, limit=8)
        if not seeds:
            return []

        refs: list[KnowledgeReference] = []
        seen: set[str] = set()
        for seed in seeds:
            sim = max(0.35, keyword_overlap_score(query, f"{seed.label} {seed.summary}"))
            refs.append(self._node_to_ref(seed, similarity=sim, via="seed"))
            seen.add(seed.id)
            for edge, neighbor in snapshot.neighbors(seed.id, hops=hops):
                if neighbor.id in seen:
                    continue
                seen.add(neighbor.id)
                n_sim = max(
                    0.25,
                    keyword_overlap_score(query, f"{neighbor.label} {neighbor.summary}") * 0.85
                    + edge.weight * 0.15,
                )
                refs.append(
                    self._node_to_ref(
                        neighbor,
                        similarity=n_sim,
                        via=f"{edge.relation.value}:{seed.id}",
                    )
                )

        refs.sort(key=lambda item: item.relevance, reverse=True)
        return refs[: max(1, top_k)]

    def _add_knowledge_item_subgraph(self, item: ProjectKnowledgeItem, project_id: UUID, add_node: Any, add_edge: Any) -> None:
        item_id = f"knowledge:{item.id}"
        dk = item.design_knowledge
        label = (dk.topic if dk and dk.topic.strip() else item.category) or "knowledge"
        summary = item.statement
        if dk is not None and dk.has_substance:
            summary = " · ".join(
                part
                for part in (
                    dk.problem,
                    dk.strategy,
                    dk.insight,
                    dk.principle,
                    dk.spatial_translation,
                )
                if part and part.strip()
            ) or summary
        add_node(
            KnowledgeNode(
                id=item_id,
                kind=KnowledgeNodeKind.KNOWLEDGE_ITEM,
                label=label[:300],
                summary=summary[:500],
                project_id=project_id,
                source_ref=item_id,
                tags=[item.category, item.origin.value],
            )
        )
        if item.linked_fact_id is not None:
            add_edge(
                relation=KnowledgeRelationKind.LINKED_FACT,
                source_id=item_id,
                target_id=f"fact:{item.linked_fact_id}",
                weight=1.0,
                evidence="linked_fact_id",
            )
        if dk is None or not dk.has_substance:
            return
        if dk.strategy.strip():
            strategy_id = f"strategy:{_slug(dk.strategy)}"
            add_node(
                KnowledgeNode(
                    id=strategy_id,
                    kind=KnowledgeNodeKind.STRATEGY,
                    label=dk.strategy.strip()[:300],
                    summary=(dk.problem or dk.insight)[:300],
                    project_id=project_id,
                    source_ref=item_id,
                )
            )
            add_edge(
                relation=KnowledgeRelationKind.EXPRESSES,
                source_id=item_id,
                target_id=strategy_id,
                weight=0.92,
                evidence="strategy",
            )
        if dk.principle.strip():
            concept_id = f"concept:{_slug(dk.principle)}"
            add_node(
                KnowledgeNode(
                    id=concept_id,
                    kind=KnowledgeNodeKind.CONCEPT,
                    label=dk.principle.strip()[:300],
                    summary=dk.insight[:300],
                    project_id=project_id,
                    source_ref=item_id,
                )
            )
            add_edge(
                relation=KnowledgeRelationKind.EXPRESSES,
                source_id=item_id,
                target_id=concept_id,
                weight=0.9,
            )
        if dk.spatial_translation.strip():
            space_id = f"space:{_slug(dk.spatial_translation)}"
            add_node(
                KnowledgeNode(
                    id=space_id,
                    kind=KnowledgeNodeKind.SPACE,
                    label=dk.spatial_translation.strip()[:300],
                    summary=dk.insight[:200],
                    project_id=project_id,
                    source_ref=item_id,
                )
            )
            add_edge(
                relation=KnowledgeRelationKind.TRANSLATES_TO,
                source_id=item_id,
                target_id=space_id,
                weight=0.95,
                evidence="spatial_translation",
            )
        if dk.material_strategy.strip():
            mat_id = f"material:{_slug(dk.material_strategy)}"
            add_node(
                KnowledgeNode(
                    id=mat_id,
                    kind=KnowledgeNodeKind.MATERIAL,
                    label=dk.material_strategy.strip()[:300],
                    project_id=project_id,
                    source_ref=item_id,
                )
            )
            add_edge(
                relation=KnowledgeRelationKind.USES,
                source_id=item_id,
                target_id=mat_id,
                weight=0.85,
                evidence="material_strategy",
            )
        from archium.domain.case_ref import case_id_from_ref

        case_id = case_id_from_ref(dk.precedent_ref)
        if case_id:
            add_edge(
                relation=KnowledgeRelationKind.INSPIRED_BY,
                source_id=item_id,
                target_id=f"case:{case_id}",
                weight=0.9,
                evidence="precedent_ref",
            )

    def _add_case_subgraph(self, case: ArchitectureCase, add_node: Any, add_edge: Any) -> None:
        case_id = f"case:{case.id}"
        add_node(
            KnowledgeNode(
                id=case_id,
                kind=KnowledgeNodeKind.CASE,
                label=case.name,
                summary=(case.strategy or case.design_problem)[:400],
                source_ref=case_id,
                tags=list(case.tags),
                extra={"architect": case.architect, "location": case.location},
            )
        )
        if case.architect.strip():
            arch_id = f"architect:{_slug(case.architect)}"
            add_node(
                KnowledgeNode(
                    id=arch_id,
                    kind=KnowledgeNodeKind.ARCHITECT,
                    label=case.architect.strip(),
                    source_ref=case_id,
                )
            )
            add_edge(
                relation=KnowledgeRelationKind.DERIVED_FROM,
                source_id=case_id,
                target_id=arch_id,
                weight=0.8,
            )
        if case.spatial_logic.strip():
            space_id = f"space:{_slug(case.spatial_logic)}"
            add_node(
                KnowledgeNode(
                    id=space_id,
                    kind=KnowledgeNodeKind.SPACE,
                    label=case.spatial_logic.strip()[:300],
                    source_ref=case_id,
                )
            )
            add_edge(
                relation=KnowledgeRelationKind.TRANSLATES_TO,
                source_id=case_id,
                target_id=space_id,
                weight=0.9,
            )
        if case.material_language.strip():
            mat_id = f"material:{_slug(case.material_language)}"
            add_node(
                KnowledgeNode(
                    id=mat_id,
                    kind=KnowledgeNodeKind.MATERIAL,
                    label=case.material_language.strip()[:300],
                    source_ref=case_id,
                )
            )
            add_edge(
                relation=KnowledgeRelationKind.USES,
                source_id=case_id,
                target_id=mat_id,
                weight=0.85,
            )
        if case.location.strip():
            region_id = f"region:{_slug(case.location)}"
            add_node(
                KnowledgeNode(
                    id=region_id,
                    kind=KnowledgeNodeKind.REGION,
                    label=case.location.strip()[:300],
                    source_ref=case_id,
                )
            )
            add_edge(
                relation=KnowledgeRelationKind.LOCATED_IN,
                source_id=case_id,
                target_id=region_id,
                weight=0.7,
            )
        for tag in case.tags:
            tag_clean = tag.strip()
            if not tag_clean:
                continue
            tag_id = f"tag:{_slug(tag_clean)}"
            add_node(
                KnowledgeNode(
                    id=tag_id,
                    kind=KnowledgeNodeKind.TAG,
                    label=tag_clean,
                    source_ref=case_id,
                    tags=[tag_clean],
                )
            )
            add_edge(
                relation=KnowledgeRelationKind.HAS_TAG,
                source_id=case_id,
                target_id=tag_id,
                weight=1.0,
            )
            # Cross-case similarity via shared tags (lazy: only tag→case reverse)
            add_edge(
                relation=KnowledgeRelationKind.SIMILAR_TO,
                source_id=tag_id,
                target_id=case_id,
                weight=0.6,
                evidence="shared_tag",
            )
        for principle in case.transferable_principles[:3]:
            if not principle.strip():
                continue
            concept_id = f"concept:{_slug(principle)}"
            add_node(
                KnowledgeNode(
                    id=concept_id,
                    kind=KnowledgeNodeKind.CONCEPT,
                    label=principle.strip()[:300],
                    source_ref=case_id,
                )
            )
            add_edge(
                relation=KnowledgeRelationKind.INSPIRED_BY,
                source_id=case_id,
                target_id=concept_id,
                weight=0.88,
            )

    @staticmethod
    def _node_to_ref(
        node: KnowledgeNode,
        *,
        similarity: float,
        via: str,
    ) -> KnowledgeReference:
        authority = {
            KnowledgeNodeKind.FACT: 0.9,
            KnowledgeNodeKind.KNOWLEDGE_ITEM: 0.75,
            KnowledgeNodeKind.CASE: 0.8,
            KnowledgeNodeKind.CONCEPT: 0.7,
            KnowledgeNodeKind.SPACE: 0.72,
            KnowledgeNodeKind.MATERIAL: 0.7,
            KnowledgeNodeKind.TAG: 0.55,
            KnowledgeNodeKind.ARCHITECT: 0.65,
            KnowledgeNodeKind.REGION: 0.6,
        }.get(node.kind, 0.55)
        transferability = {
            KnowledgeNodeKind.CONCEPT: 0.9,
            KnowledgeNodeKind.SPACE: 0.88,
            KnowledgeNodeKind.MATERIAL: 0.8,
            KnowledgeNodeKind.CASE: 0.7,
            KnowledgeNodeKind.TAG: 0.75,
            KnowledgeNodeKind.FACT: 1.0,
            KnowledgeNodeKind.KNOWLEDGE_ITEM: 0.82,
        }.get(node.kind, 0.55)
        usage = (
            KnowledgeUsage.EVIDENCE
            if node.kind == KnowledgeNodeKind.FACT
            else KnowledgeUsage.DESIGN_JUDGMENT
            if node.kind
            in {
                KnowledgeNodeKind.CONCEPT,
                KnowledgeNodeKind.SPACE,
                KnowledgeNodeKind.KNOWLEDGE_ITEM,
            }
            else KnowledgeUsage.ILLUSTRATIVE
        )
        content = node.summary or node.label
        return KnowledgeReference(
            source_kind=KnowledgeSourceKind.GRAPH_NODE,
            source_id=node.id[:80],
            content=content[:1500] or node.label,
            title=f"{node.kind.value}:{node.label}"[:200],
            similarity=similarity,
            authority=authority,
            transferability=transferability,
            relevance=rank_relevance(
                similarity=similarity,
                authority=authority,
                transferability=transferability,
                usage=usage,
            ),
            usage=usage,
            project_id=node.project_id,
            extra={
                "node_kind": node.kind.value,
                "via": via,
                "source_ref": node.source_ref,
                "tags": list(node.tags)[:8],
            },
        )

def _slug(text: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in text.strip().lower())
    cleaned = "_".join(part for part in cleaned.split("_") if part)
    return (cleaned or "x")[:80]
