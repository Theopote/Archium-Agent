"""Tests for PresentationTechnologyRadarService."""

from __future__ import annotations

from archium.application.presentation_technology_radar_catalog import DEFAULT_RADAR_SYSTEMS
from archium.application.presentation_technology_radar_service import (
    PresentationTechnologyRadarService,
    RadarFilter,
)


def test_default_catalog_has_eleven_systems() -> None:
    service = PresentationTechnologyRadarService()
    assert service.summary().total == 11
    assert len(DEFAULT_RADAR_SYSTEMS) == 11


def test_required_seed_ids_present() -> None:
    service = PresentationTechnologyRadarService()
    required = {
        "pptagent",
        "presenton",
        "presentation-ai",
        "slide-deck-ai",
        "slidebot-ai",
        "slideweaver",
        "aippt",
        "beautiful-ai",
        "plus-ai",
        "microsoft-copilot",
        "gamma",
    }
    ids = {item.id for item in service.list_systems()}
    assert required.issubset(ids)


def test_filter_by_relevance() -> None:
    service = PresentationTechnologyRadarService()
    adopt = service.list_systems(RadarFilter(relevance="adopt"))
    assert adopt
    assert all(item.archium_relevance == "adopt" for item in adopt)


def test_filter_by_query() -> None:
    service = PresentationTechnologyRadarService()
    results = service.list_systems(RadarFilter(query="gamma"))
    assert len(results) == 1
    assert results[0].id == "gamma"


def test_mark_reviewed_updates_timestamp() -> None:
    service = PresentationTechnologyRadarService()
    before = service.get_system("gamma")
    assert before is not None
    updated = service.mark_reviewed("gamma")
    assert updated.last_reviewed_at >= before.last_reviewed_at
