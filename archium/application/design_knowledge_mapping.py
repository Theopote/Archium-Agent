"""Map research findings ↔ DesignKnowledge objects."""

from __future__ import annotations

import re

from archium.domain.design_knowledge import DesignKnowledge
from archium.infrastructure.llm.research_schemas import ResearchFindingDraft

_LABEL_MAP: tuple[tuple[str, str], ...] = (
    ("原则", "principle"),
    ("principle", "principle"),
    ("空间", "spatial_translation"),
    ("spatial", "spatial_translation"),
    ("材料", "material_strategy"),
    ("构造", "material_strategy"),
    ("material", "material_strategy"),
    ("关联", "project_link"),
    ("link", "project_link"),
    ("适用", "applicability"),
    ("applicability", "applicability"),
    ("洞察", "insight"),
    ("insight", "insight"),
)


def design_knowledge_from_finding(finding: ResearchFindingDraft) -> DesignKnowledge:
    """Build DesignKnowledge from structured draft fields + labeled key_points."""
    evidence = [
        (source.title or source.url or "").strip()
        for source in finding.suggested_sources
        if (source.title or source.url or "").strip()
    ]
    evidence.extend(item.strip() for item in finding.evidence if item.strip())

    knowledge = DesignKnowledge(
        topic=(finding.topic or "").strip(),
        insight=(finding.insight or "").strip() or (finding.summary or "").strip(),
        principle=(finding.principle or "").strip(),
        spatial_translation=(finding.spatial_translation or "").strip(),
        material_strategy=(finding.material_strategy or "").strip(),
        project_link=(finding.project_link or finding.relevance or "").strip(),
        applicability=(finding.applicability or "").strip(),
        evidence=evidence,
    )
    return _merge_labeled_key_points(knowledge, finding.key_points)


def _merge_labeled_key_points(
    knowledge: DesignKnowledge,
    key_points: list[str],
) -> DesignKnowledge:
    updates: dict[str, str] = {}
    for raw in key_points:
        text = (raw or "").strip()
        if not text:
            continue
        field_name, value = _split_labeled_point(text)
        if field_name is None:
            continue
        current = getattr(knowledge, field_name) or ""
        if not str(current).strip():
            updates[field_name] = value
    if not updates:
        return knowledge
    return knowledge.model_copy(update=updates)


def _split_labeled_point(text: str) -> tuple[str | None, str]:
    match = re.match(r"^(?P<label>[^：:]+)[：:]\s*(?P<value>.+)$", text)
    if not match:
        return None, text
    label = match.group("label").strip().lower()
    value = match.group("value").strip()
    for token, field_name in _LABEL_MAP:
        if token.lower() in label or label in token.lower():
            return field_name, value
    return None, text
