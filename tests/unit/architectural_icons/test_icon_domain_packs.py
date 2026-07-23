"""Tests for icon domain packs and category folders."""

from __future__ import annotations

from archium.application.visual.architectural_icon_registry import (
    ArchitecturalIconMatcher,
    default_icon_pack_root,
    load_default_architectural_icon_registry,
)
from archium.application.visual.icon_domain_packs import (
    icons_for_domain,
    list_icon_folders,
    load_icon_domain_packs,
)


def test_pack_root_uses_assets_icons() -> None:
    root = default_icon_pack_root()
    assert root.name == "icons"
    assert (root / "manifest.json").is_file()
    assert (root / "architecture").is_dir()
    assert (root / "culture").is_dir()


def test_registry_has_minimum_thirty_icons() -> None:
    registry = load_default_architectural_icon_registry()
    icons = registry.all()
    assert len(icons) >= 30
    by_folder = {folder: registry.icons_in_folder(folder) for folder in list_icon_folders()}
    assert len(by_folder["architecture"]) >= 9
    assert len(by_folder["environment"]) >= 6
    assert len(by_folder["traffic"]) >= 7
    assert len(by_folder["energy"]) >= 4
    assert len(by_folder["culture"]) >= 7


def test_registry_has_category_folders() -> None:
    registry = load_default_architectural_icon_registry()
    assert len(registry.all()) >= 30
    traffic = registry.icons_in_folder("traffic")
    culture = registry.icons_in_folder("culture")
    assert len(traffic) >= 5
    assert len(culture) >= 4
    for icon in traffic:
        assert registry.resolve_svg_path(icon).is_file()


def test_domain_packs_hospital_and_village() -> None:
    packs = load_icon_domain_packs()
    assert "hospital" in packs
    assert "village" in packs
    assert len(packs["hospital"].icon_names) == 5
    assert len(packs["village"].icon_names) == 5

    hospital = icons_for_domain("hospital")
    village = icons_for_domain("village")
    assert {icon.canonical_name for icon in hospital} == {
        "healthcare",
        "public_transport",
        "healing_garden",
        "green_landscape",
        "pedestrian_flow",
    }
    assert {icon.canonical_name for icon in village} == {
        "heritage",
        "local_industry",
        "ecology",
        "tourism",
        "community",
    }


def test_hospital_semantic_aliases_match() -> None:
    matcher = ArchitecturalIconMatcher()
    cases = {
        "医疗": "healthcare",
        "交通": "public_transport",
        "疗愈": "healing_garden",
        "绿化": "green_landscape",
        "流线": "pedestrian_flow",
    }
    for query, expected in cases.items():
        match = matcher.match(query)
        assert match is not None, query
        assert match.icon.canonical_name == expected, query


def test_village_semantic_aliases_match() -> None:
    matcher = ArchitecturalIconMatcher()
    cases = {
        "文化": "heritage",
        "历史": "heritage",
        "产业": "local_industry",
        "生态": "ecology",
        "旅游": "tourism",
    }
    for query, expected in cases.items():
        match = matcher.match(query)
        assert match is not None, query
        assert match.icon.canonical_name == expected, query


def test_expanded_icon_aliases_match() -> None:
    matcher = ArchitecturalIconMatcher()
    cases = {
        "住宅": "residential",
        "商业": "commercial",
        "办公": "office_tower",
        "结构": "structural_system",
        "雨水": "water_system",
        "自行车": "bicycle_lane",
        "风电": "wind_power",
        "广场": "public_space",
        "手工艺": "traditional_craft",
    }
    for query, expected in cases.items():
        match = matcher.match(query)
        assert match is not None, query
        assert match.icon.canonical_name == expected, query


def test_list_icon_folders_from_manifest() -> None:
    folders = list_icon_folders()
    assert folders == ("architecture", "environment", "traffic", "energy", "culture")
