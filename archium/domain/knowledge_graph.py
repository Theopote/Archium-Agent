"""Architectural Knowledge Graph — nodes & relations (in-memory / project-scoped).

Not Neo4j: Service builds a traversable snapshot from Fact / Knowledge /
ArchitectureCase / Asset captions, then merges **confirmed** persisted edges
(Phase C). Process history stays on IntentEvolution.
"""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import Field

from archium.domain._base import DomainModel, IdentifiedModel, TimestampedModel


class KnowledgeNodeKind(StrEnum):
    BUILDING = "building"
    ARCHITECT = "architect"
    CONCEPT = "concept"
    STRATEGY = "strategy"
    MATERIAL = "material"
    SPACE = "space"
    CULTURE = "culture"
    REGION = "region"
    CLIMATE = "climate"
    TAG = "tag"
    FACT = "fact"
    KNOWLEDGE_ITEM = "knowledge_item"
    CASE = "case"
    ASSET = "asset"
    OTHER = "other"


class KnowledgeRelationKind(StrEnum):
    USES = "uses"
    RESPONDS_TO = "responds_to"
    INSPIRED_BY = "inspired_by"
    SIMILAR_TO = "similar_to"
    TRANSLATES_TO = "translates_to"
    HAS_TAG = "has_tag"
    LINKED_FACT = "linked_fact"
    DERIVED_FROM = "derived_from"
    EVIDENCE_OF = "evidence_of"
    LOCATED_IN = "located_in"
    EXPRESSES = "expresses"


class ConfirmedEdgeStatus(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"


class ConfirmedEdgeSource(StrEnum):
    USER = "user"
    RESEARCH_CONFIRM = "research_confirm"
    SYSTEM = "system"


class KnowledgeNode(DomainModel):
    id: str = Field(min_length=1, max_length=120)
    kind: KnowledgeNodeKind
    label: str = Field(min_length=1, max_length=300)
    summary: str = ""
    project_id: UUID | None = None
    source_ref: str = ""  # e.g. fact:uuid / case:therme_vals
    tags: list[str] = Field(default_factory=list)
    extra: dict[str, object] = Field(default_factory=dict)

    def to_prompt_line(self) -> str:
        bit = f"{self.kind.value}:{self.label}"
        if self.summary.strip():
            return f"{bit} — {self.summary.strip()[:160]}"
        return bit


class KnowledgeEdge(DomainModel):
    id: str = Field(min_length=1, max_length=160)
    relation: KnowledgeRelationKind
    source_id: str = Field(min_length=1, max_length=120)
    target_id: str = Field(min_length=1, max_length=120)
    weight: float = Field(default=1.0, ge=0.0, le=1.0)
    evidence: str = ""
    confirmed: bool = False


class ConfirmedKnowledgeEdge(IdentifiedModel, TimestampedModel):
    """User/research-confirmed graph edge — survives process restart (Phase C)."""

    project_id: UUID
    relation: KnowledgeRelationKind
    source_ref: str = Field(min_length=1, max_length=120)
    target_ref: str = Field(min_length=1, max_length=120)
    weight: float = Field(default=1.0, ge=0.0, le=1.0)
    evidence: str = ""
    status: ConfirmedEdgeStatus = ConfirmedEdgeStatus.ACTIVE
    source: ConfirmedEdgeSource = ConfirmedEdgeSource.USER
    knowledge_item_id: UUID | None = None

    def edge_key(self) -> str:
        return f"{self.source_ref}:{self.relation.value}:{self.target_ref}"

    def to_snapshot_edge(self) -> KnowledgeEdge:
        return KnowledgeEdge(
            id=self.edge_key()[:160],
            relation=self.relation,
            source_id=self.source_ref,
            target_id=self.target_ref,
            weight=self.weight,
            evidence=self.evidence,
            confirmed=True,
        )

    def revoke(self) -> None:
        self.status = ConfirmedEdgeStatus.REVOKED
        self.touch()


class KnowledgeGraphSnapshot(DomainModel):
    """Project (+ seed library) architectural knowledge graph."""

    project_id: UUID | None = None
    nodes: list[KnowledgeNode] = Field(default_factory=list)
    edges: list[KnowledgeEdge] = Field(default_factory=list)

    def node_map(self) -> dict[str, KnowledgeNode]:
        return {node.id: node for node in self.nodes}

    def neighbors(
        self,
        node_id: str,
        *,
        hops: int = 1,
    ) -> list[tuple[KnowledgeEdge, KnowledgeNode]]:
        """1-hop (or limited BFS) expansion."""
        by_id = self.node_map()
        if node_id not in by_id:
            return []
        frontier = {node_id}
        seen_nodes = {node_id}
        found: list[tuple[KnowledgeEdge, KnowledgeNode]] = []
        for _ in range(max(1, hops)):
            next_frontier: set[str] = set()
            for edge in self.edges:
                other: str | None = None
                if edge.source_id in frontier and edge.target_id not in seen_nodes:
                    other = edge.target_id
                elif edge.target_id in frontier and edge.source_id not in seen_nodes:
                    other = edge.source_id
                if other is None or other not in by_id:
                    continue
                found.append((edge, by_id[other]))
                seen_nodes.add(other)
                next_frontier.add(other)
            frontier = next_frontier
            if not frontier:
                break
        return found

    def match_nodes(self, query: str, *, limit: int = 12) -> list[KnowledgeNode]:
        tokens = _tokenize(query)
        if not tokens:
            return []
        scored: list[tuple[float, KnowledgeNode]] = []
        for node in self.nodes:
            hay = f"{node.label} {node.summary} {' '.join(node.tags)}".lower()
            hits = sum(1 for token in tokens if token in hay)
            if hits <= 0:
                continue
            scored.append((hits / len(tokens), node))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [node for _, node in scored[:limit]]

    def to_prompt_block(self, *, max_edges: int = 24) -> str:
        if not self.nodes:
            return ""
        lines = ["【建筑知识图谱】"]
        for node in self.nodes[:20]:
            lines.append(f"- 节点 {node.to_prompt_line()}")
        for edge in self.edges[:max_edges]:
            mark = "✓" if edge.confirmed else ""
            lines.append(
                f"- 边{mark} {edge.source_id} -[{edge.relation.value}]-> {edge.target_id}"
                + (f" ({edge.evidence[:80]})" if edge.evidence else "")
            )
        return "\n".join(lines)


def infer_node_kind_from_ref(ref: str) -> KnowledgeNodeKind:
    prefix = (ref or "").split(":", 1)[0].strip().lower()
    mapping = {
        "fact": KnowledgeNodeKind.FACT,
        "knowledge": KnowledgeNodeKind.KNOWLEDGE_ITEM,
        "case": KnowledgeNodeKind.CASE,
        "asset": KnowledgeNodeKind.ASSET,
        "concept": KnowledgeNodeKind.CONCEPT,
        "strategy": KnowledgeNodeKind.STRATEGY,
        "space": KnowledgeNodeKind.SPACE,
        "material": KnowledgeNodeKind.MATERIAL,
        "architect": KnowledgeNodeKind.ARCHITECT,
        "tag": KnowledgeNodeKind.TAG,
        "building": KnowledgeNodeKind.BUILDING,
    }
    return mapping.get(prefix, KnowledgeNodeKind.OTHER)


def _tokenize(text: str) -> list[str]:
    import re

    tokens = re.findall(r"[\w\u4e00-\u9fff]+", (text or "").lower())
    return [t for t in tokens if len(t) >= 2]
