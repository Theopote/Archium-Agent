"""Unit coverage for icon composition cases V8–V18 (builders + policy).

PPTX screenshot baselines for V8–V9 and V14 (stroke recolor) are CI-gated.
Remaining expansion cases: promote via candidate → approve-baseline.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from archium.application.visual.visual_intent_service import VisualIntentService
from archium.domain.visual.enums import LayoutContentType, LayoutElementRole, LayoutFamily
from archium.infrastructure.renderers.pptxgen.layout_plan_adapter import (
    PptxLayoutPlanAdapter,
    SlideContentBundle,
)
from tests.golden.visual.composition.artifacts import _bundle_with_icon_asset_paths
from tests.golden.visual.composition.case_builders import (
    ICON_BASELINE_CASE_IDS,
    ICON_EXPANSION_CASE_IDS,
    PPTX_VISUAL_REGRESSION_CASE_IDS,
    build_composition_case,
    build_v8_process_narrative_icons,
    build_v9_metric_dashboard_icons,
    build_v10_icons_long_cjk_title,
    build_v11_icons_dark_theme,
    build_v12_icons_light_theme,
    build_v13_icons_small_size,
    build_v14_icons_stroke_recolor,
    build_v15_icons_aspect_4x3,
    build_v16_icons_missing_fallback,
    build_v17_icons_illegal_ref,
    build_v18_icons_dense_eight_steps,
)


class _FakeIntentRepo:
    def __init__(self) -> None:
        self._items: dict = {}

    def save(self, intent):  # noqa: ANN001
        self._items[intent.id] = intent
        return intent

    def get(self, intent_id):  # noqa: ANN001
        return self._items.get(intent_id)


@pytest.fixture
def intent_service() -> VisualIntentService:
    from archium.config.settings import get_settings

    service = VisualIntentService.__new__(VisualIntentService)
    service._session = None  # noqa: SLF001
    service._llm = None  # noqa: SLF001
    service._settings = get_settings()  # noqa: SLF001
    service._intents = _FakeIntentRepo()  # noqa: SLF001
    return service


def test_icon_process_case_emits_image_arrows(intent_service: VisualIntentService) -> None:
    case = build_v8_process_narrative_icons(intent_service)
    arrows = [el for el in case.plan.elements if el.id.startswith("arrow_")]
    assert len(arrows) == 3
    assert all(el.content_type == LayoutContentType.IMAGE for el in arrows)
    assert all(str(el.content_ref).startswith("icon:") for el in arrows)
    assert case.plan.elements_by_role(LayoutElementRole.SOURCE)
    assert not case.report.has_critical()


def test_icon_metric_case_emits_decorative_icon_images(intent_service: VisualIntentService) -> None:
    case = build_v9_metric_dashboard_icons(intent_service)
    icons = [
        el
        for el in case.plan.elements
        if el.role == LayoutElementRole.DECORATION and el.content_type == LayoutContentType.IMAGE
    ]
    assert len(icons) >= 4
    assert case.plan.element_by_id("chart") is not None
    assert not case.report.has_critical()


def test_icon_baseline_cases_are_in_pptx_regression_registry() -> None:
    assert set(ICON_BASELINE_CASE_IDS).issubset(PPTX_VISUAL_REGRESSION_CASE_IDS)
    # Expansion cases are builders-only until approve-baseline promotes them.
    assert not set(ICON_EXPANSION_CASE_IDS).issubset(PPTX_VISUAL_REGRESSION_CASE_IDS)


def test_icon_case_deck_contains_svg_paths(intent_service: VisualIntentService) -> None:
    case = build_v9_metric_dashboard_icons(intent_service)
    bundle = _bundle_with_icon_asset_paths(case.plan, SlideContentBundle(page_number=1))
    payload = PptxLayoutPlanAdapter().render_deck(
        title=case.title,
        slides=[(case.plan, case.design, bundle)],
    )
    icon_elements = [
        item
        for item in payload["slides"][0]["elements"]
        if item.get("content_ref", "").startswith("icon:")
    ]
    assert icon_elements
    assert all(str(item.get("path", "")).endswith(".svg") for item in icon_elements)


@pytest.mark.parametrize("case_id", ICON_EXPANSION_CASE_IDS)
def test_icon_expansion_builders_run(intent_service: VisualIntentService, case_id: str) -> None:
    case = build_composition_case(case_id, intent_service)
    assert case.case_id == case_id
    assert case.plan.elements


def test_v10_long_cjk_title(intent_service: VisualIntentService) -> None:
    case = build_v10_icons_long_cjk_title(intent_service)
    assert len(case.slide.title) >= 40
    assert case.plan.layout_family == LayoutFamily.METRIC_DASHBOARD


def test_v11_v12_theme_variants(intent_service: VisualIntentService) -> None:
    dark = build_v11_icons_dark_theme(intent_service)
    light = build_v12_icons_light_theme(intent_service)
    assert dark.design.colors.background.lower() != light.design.colors.background.lower()


def test_v13_small_icons(intent_service: VisualIntentService) -> None:
    case = build_v13_icons_small_size(intent_service)
    icons = [
        el
        for el in case.plan.elements
        if el.role == LayoutElementRole.DECORATION
        and str(el.content_ref or "").startswith("icon:")
    ]
    assert icons
    assert all(el.width <= 0.2 and el.height <= 0.2 for el in icons)


def test_v14_stroke_recolor_applies_accent_to_icon_nodes(
    intent_service: VisualIntentService,
) -> None:
    case = build_v14_icons_stroke_recolor(intent_service)
    assert case.design.colors.accent.upper() == "#E63946"
    bundle = _bundle_with_icon_asset_paths(case.plan, SlideContentBundle(page_number=1))
    payload = PptxLayoutPlanAdapter().render_deck(
        title=case.title,
        slides=[(case.plan, case.design, bundle)],
    )
    icon_elements = [
        item
        for item in payload["slides"][0]["elements"]
        if str(item.get("content_ref", "")).startswith("icon:")
    ]
    assert icon_elements
    assert all(item.get("icon_stroke_color") == "E63946" for item in icon_elements)
    for item in icon_elements:
        recolored = Path(str(item["path"]))
        assert recolored.is_file()
        assert 'stroke="#E63946"' in recolored.read_text(encoding="utf-8")


def test_v15_aspect_4x3(intent_service: VisualIntentService) -> None:
    case = build_v15_icons_aspect_4x3(intent_service)
    assert abs(case.design.page.width / case.design.page.height - 4 / 3) < 0.05


def test_v16_missing_icon_fallback(intent_service: VisualIntentService) -> None:
    case = build_v16_icons_missing_fallback(intent_service)
    refs = [str(el.content_ref) for el in case.plan.elements if el.content_ref]
    assert any("does_not_exist" in ref for ref in refs)


def test_v17_illegal_refs_do_not_crash(intent_service: VisualIntentService) -> None:
    case = build_v17_icons_illegal_ref(intent_service)
    # Adapter must tolerate bad refs when resolving paths.
    bundle = _bundle_with_icon_asset_paths(case.plan, SlideContentBundle(page_number=1))
    payload = PptxLayoutPlanAdapter().render_deck(
        title=case.title,
        slides=[(case.plan, case.design, bundle)],
    )
    assert payload["slides"]


def test_v18_dense_eight_steps(intent_service: VisualIntentService) -> None:
    case = build_v18_icons_dense_eight_steps(intent_service)
    assert len(case.slide.key_points) >= 8
    # Layout generator may clamp visible steps; IconUsagePolicy clamps icons.
    steps = [el for el in case.plan.elements if el.id.startswith("step_")]
    assert len(steps) >= 4
    icon_arrows = [
        el
        for el in case.plan.elements
        if el.id.startswith("arrow_") and str(el.content_ref or "").startswith("icon:")
    ]
    assert len(icon_arrows) <= 5
