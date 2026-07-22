"""Tests for Presentation Technology Radar service and catalog."""

from __future__ import annotations

from archium.application.presentation_technology_radar_catalog import DEFAULT_RADAR_SYSTEMS
from archium.application.presentation_technology_radar_service import (
    PresentationTechnologyRadarService,
    RadarFilter,
)


def test_seed_catalog_has_required_systems() -> None:
    ids = {item.id for item in DEFAULT_RADAR_SYSTEMS}
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
    assert required.issubset(ids)
    assert len(DEFAULT_RADAR_SYSTEMS) >= 11


def test_filter_by_relevance() -> None:
    service = PresentationTechnologyRadarService()
    adopt = service.list_systems(RadarFilter(relevance="adopt"))
    assert adopt
    assert all(item.archium_relevance == "adopt" for item in adopt)


def test_search_by_concept() -> None:
    service = PresentationTechnologyRadarService()
    results = service.list_systems(RadarFilter(query="Before/After"))
    assert any(item.id == "presentation-ai" for item in results)


def test_summary_counts() -> None:
    service = PresentationTechnologyRadarService()
    summary = service.summary()
    assert summary.total >= 11
    assert summary.adopt_count >= 1


def test_mark_reviewed_updates_timestamp() -> None:
    service = PresentationTechnologyRadarService()
    before = service.get_system("gamma")
    assert before is not None
    updated = service.mark_reviewed("gamma")
    assert updated.last_reviewed_at >= before.last_reviewed_at
