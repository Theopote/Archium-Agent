"""Shared helpers for mission-driven and project-level research topics."""

from __future__ import annotations

from archium.domain.intent.knowledge_state import KnowledgeState
from archium.domain.project_mission import ProjectMission


def collect_mission_research_topics(mission: ProjectMission) -> list[str]:
    """Merge design_intent.research_needed and mission.research_questions without duplicates."""
    topics: list[str] = []
    seen: set[str] = set()

    if mission.design_intent is not None:
        for item in mission.design_intent.research_needed:
            _append_unique(topics, seen, item)
    for item in mission.research_questions:
        _append_unique(topics, seen, item)

    return topics


def collect_project_research_topics(
    *,
    project_name: str = "",
    project_description: str = "",
    knowledge_state: KnowledgeState | None = None,
    max_topics: int = 5,
) -> list[str]:
    """Derive research topics when Mission is absent (pre-mission cultural / context research)."""
    topics: list[str] = []
    seen: set[str] = set()
    state = knowledge_state

    if state is not None:
        for gap in state.open_unknowns:
            _append_unique(topics, seen, gap.description)
        for item in state.unknown or state.missing_information:
            _append_unique(topics, seen, item)
        for reason in state.assessment_reasons:
            axis = getattr(reason.related_axis, "value", "")
            if axis in {"research_need", "facts", "context"} or "研究" in reason.factor:
                _append_unique(topics, seen, reason.factor)
                if reason.evidence.strip():
                    _append_unique(topics, seen, reason.evidence)

        known = state.known or {}
        location = (known.get("location") or "").strip()
        ptype = (known.get("type") or "").strip()
        if location and ptype:
            _append_unique(topics, seen, f"{location}{ptype}地方文化与类型先例")
        elif location:
            _append_unique(topics, seen, f"{location}地域文化与场地语境")
        elif ptype:
            _append_unique(topics, seen, f"{ptype}类型案例与文化语境")

        dims = state.effective_dimensions()
        if dims.research_need >= 0.55 and not topics:
            _append_unique(topics, seen, "项目类型与场地文化背景")

    name = (project_name or "").strip()
    desc = (project_description or "").strip()
    seed = desc or name
    if seed:
        first = seed.splitlines()[0].strip()[:80]
        if first:
            _append_unique(topics, seen, f"{first}：地方文化与设计语境")
        if any(token in seed for token in ("寺", "庙", "礼", "禅", "文化", "遗产", "民俗")):
            _append_unique(topics, seen, "当地文化、礼仪与空间叙事先例")

    if not topics and (name or desc):
        _append_unique(topics, seen, f"{name or '项目'}背景与类型研究")

    return topics[:max_topics]


def _append_unique(topics: list[str], seen: set[str], raw: str) -> None:
    key = (raw or "").strip()
    if not key:
        return
    normalized = key.casefold()
    if normalized in seen:
        return
    seen.add(normalized)
    topics.append(key)
