"""Presentation Technology Radar service — browse and filter external systems."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from archium.application.presentation_technology_radar_catalog import DEFAULT_RADAR_SYSTEMS
from archium.domain._base import utc_now
from archium.domain.external_presentation_system import (
    ArchiumRelevance,
    ExternalPresentationSystem,
    SystemCategory,
)


@dataclass(frozen=True)
class RadarFilter:
    """Optional filters for listing radar entries."""

    relevance: ArchiumRelevance | None = None
    category: SystemCategory | None = None
    query: str | None = None
    editable_pptx_only: bool = False
    local_llm_only: bool = False


@dataclass
class RadarSummary:
    """Aggregate counts for radar dashboard."""

    total: int = 0
    by_relevance: dict[str, int] = field(default_factory=dict)
    by_category: dict[str, int] = field(default_factory=dict)
    adopt_count: int = 0
    trial_count: int = 0


class PresentationTechnologyRadarService:
    """Read-only catalog service (seed data; future: persisted overrides)."""

    def __init__(self, entries: tuple[ExternalPresentationSystem, ...] | None = None) -> None:
        self._entries = list(entries or DEFAULT_RADAR_SYSTEMS)

    def list_systems(self, radar_filter: RadarFilter | None = None) -> list[ExternalPresentationSystem]:
        items = list(self._entries)
        if radar_filter is None:
            return sorted(items, key=lambda item: (item.archium_relevance, item.name))

        if radar_filter.relevance is not None:
            items = [item for item in items if item.archium_relevance == radar_filter.relevance]
        if radar_filter.category is not None:
            items = [item for item in items if item.category == radar_filter.category]
        if radar_filter.editable_pptx_only:
            items = [item for item in items if item.editable_pptx]
        if radar_filter.local_llm_only:
            items = [item for item in items if item.local_llm]
        if radar_filter.query:
            query = radar_filter.query.strip().lower()
            items = [
                item
                for item in items
                if query in item.name.lower()
                or query in item.id.lower()
                or any(query in concept.lower() for concept in item.concepts_to_adopt)
                or any(query in concept.lower() for concept in item.concepts_to_avoid)
                or query in item.page_model.lower()
            ]
        return sorted(items, key=lambda item: (item.archium_relevance, item.name))

    def get_system(self, system_id: str) -> ExternalPresentationSystem | None:
        for item in self._entries:
            if item.id == system_id:
                return item
        return None

    def summary(self) -> RadarSummary:
        by_relevance: dict[str, int] = {}
        by_category: dict[str, int] = {}
        for item in self._entries:
            by_relevance[item.archium_relevance] = by_relevance.get(item.archium_relevance, 0) + 1
            by_category[item.category] = by_category.get(item.category, 0) + 1
        return RadarSummary(
            total=len(self._entries),
            by_relevance=by_relevance,
            by_category=by_category,
            adopt_count=by_relevance.get("adopt", 0),
            trial_count=by_relevance.get("trial", 0),
        )

    def mark_reviewed(self, system_id: str, *, reviewed_at: datetime | None = None) -> ExternalPresentationSystem:
        """Update last_reviewed_at for a catalog entry (in-memory for now)."""
        for index, item in enumerate(self._entries):
            if item.id != system_id:
                continue
            updated = item.model_copy(update={"last_reviewed_at": reviewed_at or utc_now()})
            self._entries[index] = updated
            return updated
        msg = f"Unknown radar system: {system_id}"
        raise KeyError(msg)

    def list_stale(self, *, days: int = 90) -> list[ExternalPresentationSystem]:
        cutoff = utc_now().timestamp() - days * 86400
        return [
            item
            for item in self._entries
            if item.last_reviewed_at.timestamp() < cutoff
        ]
