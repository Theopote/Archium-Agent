"""Bridge confirmed Research knowledge → SlideSpec page citations (Topic 07).

Research already stores ``SourceCitation`` (often URL-only) on
``ProjectKnowledgeItem``. Document retrieval in ``enrich_slide_citations`` cannot
see those. This service projects overlapping research cites onto analysis /
empty-cite slides — no Agent, no new workflow node.
"""

from __future__ import annotations

import re
from uuid import UUID

from sqlalchemy.orm import Session

from archium.domain.project_knowledge import ProjectKnowledgeItem
from archium.domain.slide import SlideSpec
from archium.domain.slide_role import SlideRole

_TOKEN_RE = re.compile(r"[\w\u4e00-\u9fff]{2,}")

_ANALYSIS_ROLES = frozenset(
    {
        SlideRole.PROBLEM_ANALYSIS,
        SlideRole.SITE_ANALYSIS,
        SlideRole.STRATEGY,
        SlideRole.SPATIAL_LOGIC,
        SlideRole.COMPARISON,
    }
)


def attach_research_citations_to_slide(
    session: Session,
    *,
    project_id: UUID,
    slide: SlideSpec,
    limit: int = 2,
) -> int:
    """Append best-matching confirmed research cites onto ``slide`` (mutates).

    Returns number of citations appended. No-op when slide already has cites.
    """
    if slide.source_citations:
        return 0

    items = _confirmed_research(session, project_id)
    if not items:
        return 0

    haystack = _slide_haystack(slide)
    ranked = sorted(
        ((item, _overlap_score(item, haystack)) for item in items),
        key=lambda pair: pair[1],
        reverse=True,
    )
    selected: list[ProjectKnowledgeItem] = [
        item for item, score in ranked if score > 0.0
    ][: max(1, limit)]

    # Analysis pages with no lexical hit still get the newest research cite
    # so Deliver citation_gap is not a permanent dead end when Research exists.
    if not selected and slide.slide_role in _ANALYSIS_ROLES:
        selected = items[:1]

    appended = 0
    for item in selected:
        for cite in item.source_citations[:1]:
            projected = cite.model_copy(
                update={
                    "knowledge_item_id": item.id,
                    "quote": cite.quote or item.statement[:200],
                    "confidence": min(max(cite.confidence, 0.0), 1.0),
                }
            )
            slide.source_citations.append(projected)
            appended += 1
            if appended >= limit:
                return appended
    return appended


def _confirmed_research(session: Session, project_id: UUID) -> list[ProjectKnowledgeItem]:
    from archium.application.project_knowledge_service import ProjectKnowledgeService

    return [
        item
        for item in ProjectKnowledgeService(session).list_confirmed_research_items(project_id)
        if item.source_citations
    ]


def _slide_haystack(slide: SlideSpec) -> str:
    parts = [slide.title, slide.message, *slide.key_points]
    return " ".join(part for part in parts if part)


def _item_blob(item: ProjectKnowledgeItem) -> str:
    parts = [item.statement]
    dk = item.design_knowledge
    if dk is not None:
        parts.extend(
            [
                dk.topic or "",
                dk.insight or "",
                dk.principle or "",
                dk.spatial_translation or "",
            ]
        )
    return " ".join(parts).lower()


def _overlap_score(item: ProjectKnowledgeItem, haystack: str) -> float:
    tokens = _TOKEN_RE.findall(haystack.lower())
    if not tokens:
        return 0.0
    blob = _item_blob(item)
    if not blob.strip():
        return 0.0
    hits = sum(1 for token in tokens if token in blob)
    return hits / float(len(tokens))
