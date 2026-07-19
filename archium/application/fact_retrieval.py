"""Hybrid fact lookup helpers for project context assembly."""

from __future__ import annotations

from archium.domain.fact import ProjectFact
from archium.domain.fact_ledger import STANDARD_FACT_KEY_MAP

_FACT_QUERY_HINTS: dict[str, tuple[str, ...]] = {
    "plot_ratio": ("容积率", "far", "plot ratio", "开发强度"),
    "height": ("限高", "建筑高度", "高度控制", "控高"),
    "site_area": ("用地面积", "用地", "占地面积", "land area"),
    "building_area": ("建筑面积", "总面积", "gfa"),
    "building_density": ("建筑密度", "密度"),
    "green_ratio": ("绿地率", "绿化率", "green ratio"),
    "floors": ("层数", "楼层", "floors"),
    "bed_count": ("床位", "bed"),
    "parking_count": ("停车", "车位", "parking"),
    "main_function": ("功能", "业态", "program"),
    "client_requirements": ("甲方要求", "业主要求"),
    "constraints": ("限制条件", "约束", "控制指标"),
}


def match_fact_keys_from_query(query: str) -> set[str]:
    """Return standard fact keys whose labels or hints appear in the query."""
    normalized = query.strip().lower()
    if not normalized:
        return set()
    matched: set[str] = set()
    for key, hints in _FACT_QUERY_HINTS.items():
        definition = STANDARD_FACT_KEY_MAP.get(key)
        candidates = list(hints)
        if definition is not None:
            candidates.append(definition.label)
        for hint in candidates:
            token = hint.strip().lower()
            if token and token in normalized:
                matched.add(key)
                break
    return matched


def rank_facts_for_context(
    facts: list[ProjectFact],
    *,
    query: str | None = None,
    limit: int = 30,
) -> list[ProjectFact]:
    """Order facts for prompt injection: query-relevant and confirmed first."""
    if not facts:
        return []
    query_keys = match_fact_keys_from_query(query or "")
    seen: set[str] = set()
    ranked: list[ProjectFact] = []

    def add(fact: ProjectFact) -> None:
        if fact.key in seen:
            return
        seen.add(fact.key)
        ranked.append(fact)

    for fact in facts:
        if fact.is_confirmed and fact.key in query_keys:
            add(fact)
    for fact in facts:
        if fact.is_confirmed:
            add(fact)
    for fact in facts:
        if fact.key in query_keys:
            add(fact)
    for fact in facts:
        add(fact)

    return ranked[:limit]
