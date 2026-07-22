from __future__ import annotations

import pytest
from archium.application.visual.visual_intent_service import VisualIntentService
from archium.domain.visual.enums import LayoutContentType, LayoutElementRole
from archium.infrastructure.renderers.pptxgen.layout_plan_adapter import PptxLayoutPlanAdapter
from archium.infrastructure.renderers.pptxgen.layout_plan_adapter import SlideContentBundle
from tests.golden.visual.composition.artifacts import _bundle_with_icon_asset_paths
from tests.golden.visual.composition.case_builders import (
    ICON_CASE_IDS,
    SCREENSHOT_CASE_IDS,
    build_v8_process_narrative_icons,
    build_v9_metric_dashboard_icons,
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
    service = VisualIntentService.__new__(VisualIntentService)
    service._session = None  # noqa: SLF001
    service._llm = None  # noqa: SLF001
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


def test_icon_cases_are_in_screenshot_registry() -> None:
    assert set(ICON_CASE_IDS).issubset(SCREENSHOT_CASE_IDS)


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
