"""Shared helpers for mission-driven research topics."""

from __future__ import annotations

from archium.domain.project_mission import ProjectMission


def collect_mission_research_topics(mission: ProjectMission) -> list[str]:
    """Merge design_intent.research_needed and mission.research_questions without duplicates."""
    topics: list[str] = []
    seen: set[str] = set()

    if mission.design_intent is not None:
        for item in mission.design_intent.research_needed:
            key = item.strip()
            normalized = key.casefold()
            if key and normalized not in seen:
                seen.add(normalized)
                topics.append(key)

    for item in mission.research_questions:
        key = item.strip()
        normalized = key.casefold()
        if key and normalized not in seen:
            seen.add(normalized)
            topics.append(key)

    return topics
