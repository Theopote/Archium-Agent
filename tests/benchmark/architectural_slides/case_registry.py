"""Registry of architectural slide benchmark cases."""

from __future__ import annotations

from archium.application.visual.benchmark_service import (
    BenchmarkCaseBuildRequest,
    BenchmarkSlideContent,
)
from archium.domain.slide import VisualRequirement
from archium.domain.visual.benchmark import BenchmarkCaseDefinition

from tests.benchmark.architectural_slides.case_catalog import (
    CASE_001_HERO,
    CASE_002_PHOTOS,
    CASE_003_IMAGES,
    CASE_004_CHART,
    CASE_CATALOG,
    CaseCatalogEntry,
    get_catalog_entry,
)

BENCHMARK_CASE_DEFINITIONS: tuple[BenchmarkCaseDefinition, ...] = tuple(
    entry.definition for entry in CASE_CATALOG
)
BENCHMARK_CASE_IDS: tuple[str, ...] = tuple(item.case_id for item in BENCHMARK_CASE_DEFINITIONS)

_DEFINITION_BY_ID: dict[str, BenchmarkCaseDefinition] = {
    item.case_id: item for item in BENCHMARK_CASE_DEFINITIONS
}


def get_case_definition(case_id: str) -> BenchmarkCaseDefinition:
    definition = _DEFINITION_BY_ID.get(case_id)
    if definition is None:
        msg = f"Unknown architectural benchmark case: {case_id}"
        raise ValueError(msg)
    return definition


def build_case_request(case_id: str) -> BenchmarkCaseBuildRequest:
    """Return build request for a registered benchmark case."""
    entry = get_catalog_entry(case_id)
    content = _slide_content(entry)
    return BenchmarkCaseBuildRequest(
        definition=entry.definition,
        design_system=_default_design(),
        title=entry.slide_title,
        message=entry.message,
        visual_requirements=_visual_requirements(entry),
        content=content,
        source_document=entry.source_document,
        source_page=entry.source_page,
    )


def _visual_requirements(entry: CaseCatalogEntry) -> list[VisualRequirement]:
    return [
        VisualRequirement(
            type=asset.visual_type,
            description=asset.description,
            preferred_asset_ids=[asset.asset_id],
        )
        for asset in entry.assets
    ]


def _slide_content(entry: CaseCatalogEntry) -> BenchmarkSlideContent | None:
    has_content = any(
        (
            entry.key_points,
            entry.metrics,
            entry.captions,
            entry.insight,
            entry.hero_asset_id,
            entry.supporting_asset_ids,
            entry.dominant_content_type,
            entry.preferred_layout_families,
            entry.drawing_hero,
        )
    )
    if not has_content:
        return None
    return BenchmarkSlideContent(
        key_points=list(entry.key_points) if entry.key_points else None,
        metrics=list(entry.metrics) if entry.metrics else None,
        captions=list(entry.captions) if entry.captions else None,
        insight=entry.insight,
        hero_asset_id=entry.hero_asset_id,
        supporting_asset_ids=list(entry.supporting_asset_ids) if entry.supporting_asset_ids else None,
        dominant_content_type=entry.dominant_content_type,
        preferred_layout_families=list(entry.preferred_layout_families)
        if entry.preferred_layout_families
        else None,
        drawing_hero=entry.drawing_hero,
    )


def _default_design():
    from archium.domain.visual import default_presentation_design_system

    return default_presentation_design_system()


__all__ = [
    "BENCHMARK_CASE_DEFINITIONS",
    "BENCHMARK_CASE_IDS",
    "CASE_001_HERO",
    "CASE_002_PHOTOS",
    "CASE_003_IMAGES",
    "CASE_004_CHART",
    "build_case_request",
    "get_case_definition",
]
