"""Architectural Asset Library — catalog + formula + context suggestion tests."""

from __future__ import annotations

from archium.application.visual.showcase_case_001 import build_case_001_render_bundle
from archium.domain.visual.architectural_assets import (
    NORTH_ARROW,
    PEDESTRIAN_FLOW,
    SCALE_BAR,
    SUN_PATH,
    ArchitecturalAsset,
    AssetTier,
    assets_for_formula,
    assets_for_slide_context,
    get_asset,
    list_assets,
)


def test_catalog_has_17_assets() -> None:
    all_assets = list_assets()
    assert len(all_assets) == 17
    ids = {a.id for a in all_assets}
    assert "sun_path" in ids
    assert "north_arrow" in ids
    assert "blueprint_noise" in ids


def test_tier_filter() -> None:
    analysis = list_assets(tier=AssetTier.ANALYSIS_SYMBOL)
    drawing = list_assets(tier=AssetTier.DRAWING_NOTATION)
    texture = list_assets(tier=AssetTier.DECORATIVE_TEXTURE)
    assert len(analysis) == 7
    assert len(drawing) == 6
    assert len(texture) == 4


def test_get_asset_by_id() -> None:
    a = get_asset("dimension_line")
    assert a is not None
    assert a.tier == AssetTier.DRAWING_NOTATION
    assert a.label_zh == "尺寸标注"


def test_assets_for_site_formula() -> None:
    assets = assets_for_formula("site_layer_analysis")
    ids = [a.id for a in assets]
    assert "sun_path" in ids
    assert "north_arrow" in ids
    assert "pedestrian_flow" in ids


def test_assets_for_masterplan_formula() -> None:
    assets = assets_for_formula("masterplan_focus")
    ids = [a.id for a in assets]
    assert "north_arrow" in ids
    assert "scale_bar" in ids
    assert "grid" in ids


def test_context_suggests_north_arrow_for_site() -> None:
    assets = assets_for_slide_context(title="区位与交通", has_site_plan=True)
    ids = [a.id for a in assets]
    assert "north_arrow" in ids
    assert "scale_bar" in ids
    assert "dimension_line" in ids


def test_context_suggests_pedestrian_flow_for_circulation() -> None:
    assets = assets_for_slide_context(title="流线冲突")
    ids = [a.id for a in assets]
    assert "pedestrian_flow" in ids


def test_context_suggests_section_cut() -> None:
    assets = assets_for_slide_context(title="剖面分析", has_section=True)
    ids = [a.id for a in assets]
    assert "section_cut" in ids


def test_asset_as_dict() -> None:
    d = NORTH_ARROW.as_dict()
    assert d["tier"] == "drawing_notation"
    assert d["placement"] == "corner"
    assert d["icon_ref"] == "icon:north_arrow"


def test_case_001_site_page_has_assets() -> None:
    bundle = build_case_001_render_bundle()
    site_idx = next(i for i, s in enumerate(bundle.slides) if s.title == "区位与交通")
    direction = bundle.intents[site_idx].page_direction
    assert direction is not None
    assert direction.visual_language is not None
    asset_ids = direction.visual_language.asset_ids
    assert "north_arrow" in asset_ids or "scale_bar" in asset_ids


def test_case_001_conflict_page_has_flow_asset() -> None:
    bundle = build_case_001_render_bundle()
    idx = next(i for i, s in enumerate(bundle.slides) if s.title == "流线冲突")
    direction = bundle.intents[idx].page_direction
    assert direction is not None
    assert direction.visual_language is not None
    assert "pedestrian_flow" in direction.visual_language.asset_ids
