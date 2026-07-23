"""Golden visual composition cases V19–V22 — Architectural Visual Grammar archetypes."""

from __future__ import annotations

from pathlib import Path

import pytest
from archium.application.visual.visual_intent_service import VisualIntentService
from archium.config.settings import get_settings
from archium.domain.visual import LayoutFamily
from archium.domain.visual.enums import CropPolicy, ImageFit, LayoutElementRole
from archium.domain.visual.visual_grammar import PageArchetype
from tests.golden.visual.composition.artifacts import UPDATE_ENV, assert_or_update_baseline
from tests.golden.visual.composition.case_builders import (
    ARCHETYPE_CASE_IDS,
    build_composition_case,
)

pytestmark = [pytest.mark.preview_visual_regression]

GOLDEN_ROOT = Path(__file__).resolve().parent


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
    service._settings = get_settings()  # noqa: SLF001
    service._intents = _FakeIntentRepo()  # noqa: SLF001
    return service


def test_v19_site_context_analysis(intent_service: VisualIntentService) -> None:
    case = build_composition_case("v19_site_context_analysis", intent_service)
    assert case.intent.page_archetype == PageArchetype.SITE_CONTEXT_ANALYSIS
    assert case.plan.layout_family == LayoutFamily.HYBRID_CANVAS
    assert case.plan.layout_variant == "site_context"
    assert case.plan.balance_strategy == "site_context_split"
    hero = case.plan.element_by_id("hero")
    assert hero is not None
    assert hero.fit_mode == ImageFit.CONTAIN
    assert hero.crop_policy == CropPolicy.FORBIDDEN
    assert case.plan.element_by_id("conclusion") is not None
    assert not case.report.has_critical()
    assert_or_update_baseline(
        GOLDEN_ROOT / case.case_id,
        plan=case.plan,
        report=case.report,
        design=case.design,
        title=case.title,
    )


def test_v20_site_problem_diagnosis(intent_service: VisualIntentService) -> None:
    case = build_composition_case("v20_site_problem_diagnosis", intent_service)
    assert case.intent.page_archetype == PageArchetype.SITE_PROBLEM_DIAGNOSIS
    assert case.plan.layout_variant == "diagnosis_split"
    assert case.plan.element_by_id("problem_tags") is not None
    assert case.plan.element_by_id("analysis") is not None
    assert len(case.plan.elements_by_role(LayoutElementRole.SUPPORTING_VISUAL)) >= 1
    assert not case.report.has_critical()
    assert_or_update_baseline(
        GOLDEN_ROOT / case.case_id,
        plan=case.plan,
        report=case.report,
        design=case.design,
        title=case.title,
    )


def test_v21_design_strategy(intent_service: VisualIntentService) -> None:
    case = build_composition_case("v21_design_strategy", intent_service)
    assert case.intent.page_archetype == PageArchetype.DESIGN_STRATEGY
    assert case.plan.layout_variant == "strategy_concept"
    assert case.plan.element_by_id("concept") is not None
    assert case.plan.element_by_id("spatial_change") is not None
    assert len([el for el in case.plan.elements if el.id.startswith("card_")]) == 3
    assert not case.report.has_critical()
    assert_or_update_baseline(
        GOLDEN_ROOT / case.case_id,
        plan=case.plan,
        report=case.report,
        design=case.design,
        title=case.title,
    )


def test_v22_before_after_transformation(intent_service: VisualIntentService) -> None:
    case = build_composition_case("v22_before_after_transformation", intent_service)
    assert case.intent.page_archetype == PageArchetype.BEFORE_AFTER_TRANSFORMATION
    assert case.plan.layout_variant == "before_after"
    assert case.plan.balance_strategy == "before_after"
    visuals = case.plan.elements_by_role(LayoutElementRole.SUPPORTING_VISUAL)
    assert len(visuals) == 2
    assert len({round(el.width, 3) for el in visuals}) == 1
    assert not case.report.has_critical()
    assert_or_update_baseline(
        GOLDEN_ROOT / case.case_id,
        plan=case.plan,
        report=case.report,
        design=case.design,
        title=case.title,
    )


def test_archetype_case_registry() -> None:
    assert len(ARCHETYPE_CASE_IDS) == 4


def test_update_env_documented() -> None:
    assert UPDATE_ENV == "UPDATE_VISUAL_COMPOSITION_GOLDENS"
