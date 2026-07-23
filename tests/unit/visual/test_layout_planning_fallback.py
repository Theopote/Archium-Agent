"""Unit tests for LayoutPlanningService LLM fallback warnings."""

from __future__ import annotations

from uuid import uuid4

import pytest
from archium.application.visual.layout_planning_service import (
    LAYOUT_DECISION_LLM_FALLBACK,
    LayoutPlanningService,
    format_layout_decision_warnings,
)
from archium.config.settings import get_settings
from archium.domain.slide import SlideSpec
from archium.domain.visual import VisualContentType, default_presentation_design_system
from archium.domain.visual.enums import DensityLevel, LayoutFamily
from archium.domain.visual.visual_intent import VisualIntent
from archium.exceptions import StructuredOutputError
from archium.infrastructure.llm.base import LLMRequest
from archium.infrastructure.llm.visual_schemas import LayoutDecisionDraft


class _BoomLLM:
    provider_name = "mock-provider"
    model = "mock-model"

    def generate_structured(self, request: LLMRequest, schema: type):  # noqa: ANN001
        raise StructuredOutputError("schema validation failed: missing layout_family")


class _AuthFailLLM:
    def __init__(self) -> None:
        self._settings = type(
            "S",
            (),
            {"llm_provider": "openai-compatible", "llm_model": "gemini-flash"},
        )()

    def generate_structured(self, request: LLMRequest, schema: type):  # noqa: ANN001
        raise RuntimeError("Incorrect API key provided: sk-SECRETSHOULDNOTAPPEAR")


class _BadFamilyLLM:
    provider_name = "mock-provider"
    model = "mock-model"

    def generate_structured(self, request: LLMRequest, schema: type):  # noqa: ANN001
        return LayoutDecisionDraft(
            layout_family="not_a_real_family",
            layout_variant="nope",
        )


def _intent() -> VisualIntent:
    return VisualIntent(
        slide_id=uuid4(),
        communication_goal="说明总平面结构",
        audience_takeaway="记住轴线与公服节点",
        visual_priority="图纸为主",
        dominant_content_type=VisualContentType.SITE_PLAN,
        preferred_layout_families=[LayoutFamily.DRAWING_FOCUS],
        density_level=DensityLevel.BALANCED,
    )


def _slide() -> SlideSpec:
    return SlideSpec(
        presentation_id=uuid4(),
        chapter_id="ch",
        order=0,
        title="总平面",
        message="轴线贯通。",
    )


def _service(llm: object) -> LayoutPlanningService:
    service = LayoutPlanningService.__new__(LayoutPlanningService)
    service._session = None  # noqa: SLF001
    service._llm = llm  # noqa: SLF001
    service._validator = None  # noqa: SLF001
    service._solver = None  # noqa: SLF001
    from archium.infrastructure.layout.layout_family_registry import get_layout_family_registry

    service._registry = get_layout_family_registry()  # noqa: SLF001
    service._plans = None  # noqa: SLF001
    service._intents = None  # noqa: SLF001
    service._art = None  # noqa: SLF001
    service._design = None  # noqa: SLF001
    service._settings = get_settings()  # noqa: SLF001
    service._warnings = []  # noqa: SLF001
    return service


def test_llm_exception_records_structured_fallback_warning(caplog: pytest.LogCaptureFixture) -> None:
    service = _service(_BoomLLM())
    design = default_presentation_design_system()
    with caplog.at_level("WARNING"):
        decisions = service._decide_candidates(  # noqa: SLF001
            _slide(), _intent(), None, design, candidate_count=2
        )
    assert decisions
    warnings = service.drain_warnings()
    assert len(warnings) == 1
    payload = warnings[0]
    assert payload["code"] == LAYOUT_DECISION_LLM_FALLBACK
    assert payload["provider"] == "mock-provider"
    assert payload["model"] == "mock-model"
    assert payload["error_type"] == "StructuredOutputError"
    assert payload["fallback_family"] == LayoutFamily.DRAWING_FOCUS.value
    lines = format_layout_decision_warnings(warnings)
    assert any(LAYOUT_DECISION_LLM_FALLBACK in line for line in lines)
    assert warnings[0]["error_type"] == "StructuredOutputError"
    assert "sk-" not in caplog.text
    assert "LAYOUT_PLAN_SYSTEM" not in caplog.text


def test_api_key_error_does_not_log_secret(caplog: pytest.LogCaptureFixture) -> None:
    service = _service(_AuthFailLLM())
    design = default_presentation_design_system()
    with caplog.at_level("WARNING"):
        service._decide_candidates(_slide(), _intent(), None, design, 1)  # noqa: SLF001
    warnings = service.drain_warnings()
    assert warnings[0]["error_type"] == "RuntimeError"
    assert warnings[0]["provider"] == "openai-compatible"
    assert warnings[0]["model"] == "gemini-flash"
    assert "sk-SECRET" not in caplog.text
    assert "SECRETSHOULDNOTAPPEAR" not in str(warnings)


def test_disallowed_family_records_fallback_warning() -> None:
    service = _service(_BadFamilyLLM())
    design = default_presentation_design_system()
    decisions = service._decide_candidates(_slide(), _intent(), None, design, 1)  # noqa: SLF001
    assert decisions[0].layout_family != "not_a_real_family"
    warnings = service.drain_warnings()
    assert warnings[0]["error_type"] == "DisallowedLayoutFamily"
    assert "llm_family=not_a_real_family" in warnings[0]["detail"]
