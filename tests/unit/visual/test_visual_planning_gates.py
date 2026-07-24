"""VP-003 / VP-004 visual planning gate tests."""

from __future__ import annotations

from uuid import uuid4

import pytest
from archium.application.visual.layout_planning_service import (
    LayoutPlanningService,
    capacity_blocker_messages,
)
from archium.application.visual.layout_validation_service import LayoutValidationService
from archium.application.visual.slide_capacity_service import SlideCapacityService
from archium.application.visual.visual_intent_service import VisualIntentService
from archium.config.settings import Settings
from archium.domain.enums import ApprovalStatus, SlideType
from archium.domain.slide import SlideSpec
from archium.domain.slide_design_brief import SlideDesignBrief
from archium.domain.visual.defaults import default_presentation_design_system
from archium.domain.visual.enums import DensityLevel, LayoutFamily, VisualContentType
from archium.domain.visual.slide_capacity_budget import (
    CAPACITY_IMPOSSIBLE_RULE,
    CAPACITY_OVERLOAD_RULE,
    CapacityStatus,
)
from archium.domain.visual.visual_intent import VisualIntent
from archium.exceptions import ValidationError
from archium.infrastructure.layout.layout_family_registry import get_layout_family_registry
from archium.infrastructure.layout.layout_solver import LayoutSolver


def _overloaded_slide() -> SlideSpec:
    return SlideSpec.model_construct(
        id=uuid4(),
        presentation_id=uuid4(),
        lineage_id=uuid4(),
        logical_key="ch1-p0",
        chapter_id="ch1",
        order=0,
        title="容量超载页",
        message=("这是需要占据大量垂直空间的冗长论述内容" * 40),
        slide_type=SlideType.CONTENT,
        layout_id="default",
        key_points=[("要点说明" * 30) for _ in range(8)],
        visual_requirements=[],
        source_citations=[],
        version=1,
    )


def _intent(slide: SlideSpec) -> VisualIntent:
    return VisualIntent(
        slide_id=slide.id,
        presentation_id=slide.presentation_id,
        communication_goal="说明",
        audience_takeaway="记住要点",
        visual_priority="body",
        dominant_content_type=VisualContentType.TEXT_ARGUMENT,
        preferred_layout_families=[LayoutFamily.TEXTUAL_ARGUMENT],
        density_level=DensityLevel.BALANCED,
    )


class _FakeIntentRepo:
    def __init__(self, intent: VisualIntent) -> None:
        self._intent = intent

    def get(self, _intent_id) -> VisualIntent | None:  # noqa: ANN001
        return self._intent


class _FakeDesignRepo:
    def __init__(self, design) -> None:  # noqa: ANN001
        self._design = design

    def get(self, _design_id) -> object | None:  # noqa: ANN001
        return self._design


def _layout_service(*, block_overloaded: bool) -> LayoutPlanningService:
    settings = Settings(visual_capacity_block_overloaded=block_overloaded)
    service = LayoutPlanningService.__new__(LayoutPlanningService)
    service._session = None  # noqa: SLF001
    service._llm = None  # noqa: SLF001
    service._validator = LayoutValidationService()  # noqa: SLF001
    service._solver = LayoutSolver()  # noqa: SLF001
    service._registry = get_layout_family_registry()  # noqa: SLF001
    service._plans = None  # noqa: SLF001
    service._art = None  # noqa: SLF001
    service._projects = None  # noqa: SLF001
    service._settings = settings  # noqa: SLF001
    service._warnings = []  # noqa: SLF001
    from archium.application.visual.slide_capacity_service import SlideCapacityService

    service._capacity = SlideCapacityService()  # noqa: SLF001
    service._last_capacity_budget = None  # noqa: SLF001
    from archium.application.visual.layout_style_preference import LayoutStylePreference

    service._last_style_preference = LayoutStylePreference()  # noqa: SLF001
    return service


def test_capacity_budget_blocks_overloaded_when_enabled() -> None:
    design = default_presentation_design_system()
    budget = SlideCapacityService().estimate(_overloaded_slide(), design)
    assert budget.status in {CapacityStatus.OVERLOADED, CapacityStatus.IMPOSSIBLE}
    assert budget.blocks_layout_candidates(block_overloaded=True)
    if budget.status == CapacityStatus.OVERLOADED:
        assert not budget.blocks_layout_candidates(block_overloaded=False)
    else:
        assert budget.blocks_layout_candidates(block_overloaded=False)


def test_overloaded_blocks_layout_candidates_by_default() -> None:
    slide = _overloaded_slide()
    intent = _intent(slide)
    design = default_presentation_design_system()
    budget = SlideCapacityService().estimate(slide, design)
    service = _layout_service(block_overloaded=True)
    service._intents = _FakeIntentRepo(intent)  # noqa: SLF001
    service._design = _FakeDesignRepo(design)  # noqa: SLF001

    candidates = service.generate_candidates(
        slide=slide,
        visual_intent_id=intent.id,
        art_direction_id=None,
        design_system_id=design.id,
        candidate_count=3,
    )
    warnings = service.drain_warnings()
    assert candidates == []
    expected_code = (
        CAPACITY_IMPOSSIBLE_RULE
        if budget.status == CapacityStatus.IMPOSSIBLE
        else CAPACITY_OVERLOAD_RULE
    )
    assert any(item.get("code") == expected_code for item in warnings)
    blockers = capacity_blocker_messages(warnings)
    assert len(blockers) == 1
    assert expected_code in blockers[0]


def test_overloaded_allows_candidates_when_setting_disabled() -> None:
    slide = _overloaded_slide()
    intent = _intent(slide)
    design = default_presentation_design_system()
    budget = SlideCapacityService().estimate(slide, design)
    service = _layout_service(block_overloaded=False)
    service._intents = _FakeIntentRepo(intent)  # noqa: SLF001
    service._design = _FakeDesignRepo(design)  # noqa: SLF001

    candidates = service.generate_candidates(
        slide=slide,
        visual_intent_id=intent.id,
        art_direction_id=None,
        design_system_id=design.id,
        candidate_count=3,
    )
    warnings = service.drain_warnings()
    if budget.status == CapacityStatus.IMPOSSIBLE:
        assert candidates == []
        assert any(item.get("code") == CAPACITY_IMPOSSIBLE_RULE for item in warnings)
        return
    assert candidates
    assert capacity_blocker_messages(warnings) == []
    overload = next(item for item in warnings if item.get("code") == CAPACITY_OVERLOAD_RULE)
    assert overload.get("severity") == "major"


def test_capacity_blocker_messages_still_blocks_impossible() -> None:
    warnings = [
        {"code": CAPACITY_OVERLOAD_RULE, "severity": "major", "detail": "not a blocker"},
        {
            "code": CAPACITY_IMPOSSIBLE_RULE,
            "severity": "blocker",
            "detail": "drawing exceeds canvas",
        },
    ]
    messages = capacity_blocker_messages(warnings)
    assert len(messages) == 1
    assert CAPACITY_IMPOSSIBLE_RULE in messages[0]


def test_visual_intent_requires_approved_brief_when_gate_on() -> None:
    slide = SlideSpec(
        presentation_id=uuid4(),
        chapter_id="ch1",
        order=0,
        title="测试页",
        message="内容。",
    )
    service = VisualIntentService.__new__(VisualIntentService)
    service._settings = Settings(visual_require_approved_design_brief=True)  # noqa: SLF001

    with pytest.raises(ValidationError, match="approved SlideDesignBrief"):
        VisualIntentService._require_approved_design_brief(  # noqa: SLF001
            slide,
            None,
            required=True,
        )

    pending = SlideDesignBrief(
        page_order=0,
        page_task="展示内容",
        central_claim="核心观点",
        status=ApprovalStatus.PENDING,
    )
    with pytest.raises(ValidationError, match="approved SlideDesignBrief"):
        VisualIntentService._require_approved_design_brief(  # noqa: SLF001
            slide,
            pending,
            required=True,
        )

    approved = pending.model_copy(update={"status": ApprovalStatus.APPROVED})
    VisualIntentService._require_approved_design_brief(  # noqa: SLF001
        slide,
        approved,
        required=True,
    )


def test_visual_intent_gate_off_allows_missing_brief() -> None:
    slide = SlideSpec(
        presentation_id=uuid4(),
        chapter_id="ch1",
        order=0,
        title="测试页",
        message="内容。",
    )
    VisualIntentService._require_approved_design_brief(  # noqa: SLF001
        slide,
        None,
        required=False,
    )
