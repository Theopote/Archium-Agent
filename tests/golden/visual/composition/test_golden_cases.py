"""Golden visual composition cases V1–V7 (LayoutPlan + validation + preview artifacts)."""

from __future__ import annotations

from pathlib import Path

import pytest
from archium.application.visual.visual_intent_service import VisualIntentService
from archium.domain.visual import LayoutFamily, VisualContentType
from archium.domain.visual.enums import CropPolicy, ImageFit, LayoutElementRole
from tests.golden.visual.composition.artifacts import UPDATE_ENV, assert_or_update_baseline
from tests.golden.visual.composition.case_builders import (
    COMPOSITION_CASE_IDS,
    build_composition_case,
)

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
def intent_service(monkeypatch: pytest.MonkeyPatch) -> VisualIntentService:
    service = VisualIntentService.__new__(VisualIntentService)
    service._session = None  # noqa: SLF001
    service._llm = None  # noqa: SLF001
    service._intents = _FakeIntentRepo()  # noqa: SLF001
    return service


def test_v1_drawing_focus_site_plan(intent_service: VisualIntentService) -> None:
    case = build_composition_case("v1_drawing_focus", intent_service)
    assert case.intent.dominant_content_type == VisualContentType.SITE_PLAN
    assert LayoutFamily.DRAWING_FOCUS in case.intent.preferred_layout_families

    hero = case.plan.element_by_id("hero")
    assert hero is not None
    assert hero.fit_mode == ImageFit.CONTAIN
    assert hero.crop_policy == CropPolicy.FORBIDDEN
    assert case.plan.elements_by_role(LayoutElementRole.SOURCE)
    assert case.plan.elements_by_role(LayoutElementRole.TITLE)
    assert not case.report.has_critical()
    assert_or_update_baseline(
        GOLDEN_ROOT / case.case_id,
        plan=case.plan,
        report=case.report,
        design=case.design,
        title=case.title,
    )


def test_v2_evidence_board_photos(intent_service: VisualIntentService) -> None:
    case = build_composition_case("v2_evidence_board", intent_service)
    assert case.intent.dominant_content_type == VisualContentType.PHOTO_EVIDENCE
    assert LayoutFamily.EVIDENCE_BOARD in case.intent.preferred_layout_families

    photos_els = case.plan.elements_by_role(LayoutElementRole.SUPPORTING_VISUAL)
    assert len(photos_els) == 4
    assert len({round(el.width, 3) for el in photos_els}) == 1
    assert case.plan.elements_by_role(LayoutElementRole.LEAD_STATEMENT)
    assert not case.report.has_critical()
    assert_or_update_baseline(
        GOLDEN_ROOT / case.case_id,
        plan=case.plan,
        report=case.report,
        design=case.design,
        title=case.title,
    )


def test_v3_comparative_matrix(intent_service: VisualIntentService) -> None:
    case = build_composition_case("v3_comparative_matrix", intent_service)
    assert case.plan.layout_family == LayoutFamily.COMPARATIVE_MATRIX
    images = case.plan.elements_by_role(LayoutElementRole.SUPPORTING_VISUAL)
    assert len(images) == 3
    assert len({round(img.width, 3) for img in images}) == 1
    assert case.plan.elements_by_role(LayoutElementRole.LEAD_STATEMENT)
    assert not case.report.has_critical()
    assert_or_update_baseline(
        GOLDEN_ROOT / case.case_id,
        plan=case.plan,
        report=case.report,
        design=case.design,
        title=case.title,
    )


def test_v4_analytical_diagram(intent_service: VisualIntentService) -> None:
    case = build_composition_case("v4_analytical_diagram", intent_service)
    assert case.plan.layout_family == LayoutFamily.ANALYTICAL_DIAGRAM
    assert case.plan.element_by_id("hero") is not None
    assert case.plan.element_by_id("legend") is not None
    assert len([el for el in case.plan.elements if el.id.startswith("conclusion_")]) == 3
    assert case.plan.elements_by_role(LayoutElementRole.SOURCE)
    assert not case.report.has_critical()
    assert_or_update_baseline(
        GOLDEN_ROOT / case.case_id,
        plan=case.plan,
        report=case.report,
        design=case.design,
        title=case.title,
    )


def test_v5_process_narrative(intent_service: VisualIntentService) -> None:
    case = build_composition_case("v5_process_narrative", intent_service)
    assert case.plan.layout_family == LayoutFamily.PROCESS_NARRATIVE
    assert len([el for el in case.plan.elements if el.id.startswith("step_")]) == 4
    assert len([el for el in case.plan.elements if el.id.startswith("stage_visual_")]) == 4
    assert len([el for el in case.plan.elements if el.id.startswith("arrow_")]) == 3
    assert case.plan.element_by_id("summary") is not None
    assert not case.report.has_critical()
    assert_or_update_baseline(
        GOLDEN_ROOT / case.case_id,
        plan=case.plan,
        report=case.report,
        design=case.design,
        title=case.title,
    )


def test_v6_metric_dashboard(intent_service: VisualIntentService) -> None:
    case = build_composition_case("v6_metric_dashboard", intent_service)
    assert case.plan.layout_family == LayoutFamily.METRIC_DASHBOARD
    assert len(case.plan.elements_by_role(LayoutElementRole.METRIC)) == 5
    assert case.plan.element_by_id("chart") is not None
    assert case.plan.elements_by_role(LayoutElementRole.LEAD_STATEMENT)
    assert not case.report.has_critical()
    assert_or_update_baseline(
        GOLDEN_ROOT / case.case_id,
        plan=case.plan,
        report=case.report,
        design=case.design,
        title=case.title,
    )


def test_v7_hybrid_canvas(intent_service: VisualIntentService) -> None:
    case = build_composition_case("v7_hybrid_canvas", intent_service)
    assert case.plan.layout_family == LayoutFamily.HYBRID_CANVAS
    hero = case.plan.element_by_id("hero")
    assert hero is not None
    assert hero.fit_mode == ImageFit.CONTAIN
    assert hero.crop_policy == CropPolicy.FORBIDDEN
    assert len(case.plan.elements_by_role(LayoutElementRole.SUPPORTING_VISUAL)) == 2
    assert len(case.plan.elements_by_role(LayoutElementRole.METRIC)) >= 1
    assert case.plan.elements_by_role(LayoutElementRole.CAPTION)
    assert case.plan.elements_by_role(LayoutElementRole.BODY_TEXT) or case.plan.elements_by_role(
        LayoutElementRole.LEAD_STATEMENT
    )
    assert not case.report.has_critical()
    assert_or_update_baseline(
        GOLDEN_ROOT / case.case_id,
        plan=case.plan,
        report=case.report,
        design=case.design,
        title=case.title,
    )


def test_update_env_documented() -> None:
    """Keep the update env name discoverable for operators."""
    assert UPDATE_ENV == "UPDATE_VISUAL_COMPOSITION_GOLDENS"


def test_composition_case_registry_covers_all_tests() -> None:
    assert len(COMPOSITION_CASE_IDS) == 7
