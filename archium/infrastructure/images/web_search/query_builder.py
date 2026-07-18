"""Build stock-photo search queries from slide context."""

from __future__ import annotations

from archium.domain.enums import VisualType
from archium.domain.fact import ProjectFact
from archium.domain.slide import SlideSpec, VisualRequirement

_TYPE_HINTS: dict[VisualType, str] = {
    VisualType.RENDERING: "architecture rendering building",
    VisualType.SITE_PHOTO: "architecture building exterior site",
    VisualType.REFERENCE_CASE: "architecture project case study",
}

_MAX_QUERY_LEN = 120


def build_search_query(
    slide: SlideSpec,
    requirement: VisualRequirement,
    *,
    facts: list[ProjectFact] | None = None,
) -> str:
    """Combine visual type, requirement text, and slide title into one query."""
    parts: list[str] = []
    hint = _TYPE_HINTS.get(requirement.type)
    if hint:
        parts.append(hint)

    description = requirement.description.strip()
    if description:
        parts.append(description)

    title = slide.title.strip()
    if title and title not in description:
        parts.append(title)

    message = slide.message.strip()
    if message and message not in description and message != title:
        parts.append(message)

    if facts:
        for fact in facts[:2]:
            value = fact.value.strip()
            if value and len(value) <= 40:
                parts.append(value)

    query = " ".join(part for part in parts if part).strip()
    if not query:
        query = "modern architecture"
    return query[:_MAX_QUERY_LEN]
