"""Tests for transaction repository protocols and immutable layout bumps."""

from __future__ import annotations

from uuid import uuid4

from archium.application.visual.transaction_immutability import (
    bumped_layout_plan,
    restored_from_snapshot,
)
from archium.domain.visual.enums import (
    DensityLevel,
    LayoutContentType,
    LayoutElementRole,
    LayoutFamily,
    VisualContentType,
)
from archium.domain.visual.layout import LayoutElement, LayoutPlan
from archium.domain.visual.slide_edit_snapshot import SlideEditSnapshot
from archium.domain.visual.visual_intent import VisualIntent
from archium.infrastructure.database.repositories import PresentationRepository
from archium.infrastructure.database.visual_repositories import (
    LayoutPlanRepository,
    VisualIntentRepository,
)


def test_slide_edit_snapshot_is_distinct_from_slide_spec_module() -> None:
    snapshot = SlideEditSnapshot(
        slide_id=uuid4(),
        presentation_id=uuid4(),
        visual_intent=None,
        layout_plan=None,
    )
    assert snapshot.has_layout_plan is False
    assert snapshot.has_visual_intent is False


def test_bumped_layout_plan_returns_new_instance() -> None:
    element = LayoutElement(
        id="hero",
        role=LayoutElementRole.HERO_VISUAL,
        content_type=LayoutContentType.IMAGE,
        x=1,
        y=1,
        width=4,
        height=3,
    )
    original = LayoutPlan(
        slide_id=uuid4(),
        layout_family=LayoutFamily.HERO,
        layout_variant="default",
        page_width=10,
        page_height=5.625,
        elements=[element],
        design_system_id=uuid4(),
        visual_intent_id=uuid4(),
    )
    updated_element = element.model_copy(update={"width": 5})
    bumped = bumped_layout_plan(original, elements=[updated_element])

    assert bumped is not original
    assert bumped.version == original.version + 1
    assert bumped.updated_at >= original.updated_at
    assert original.elements[0].width == 4
    assert bumped.elements[0].width == 5


def test_restored_from_snapshot_does_not_mutate_validated_model() -> None:
    intent = VisualIntent(
        slide_id=uuid4(),
        communication_goal="说明结构",
        audience_takeaway="记住轴线",
        visual_priority="图纸",
        dominant_content_type=VisualContentType.SITE_PLAN,
        preferred_layout_families=[LayoutFamily.DRAWING_FOCUS],
        density_level=DensityLevel.BALANCED,
    )
    validated = VisualIntent.model_validate(intent.model_dump(mode="json"))
    before_updated_at = validated.updated_at
    restored = restored_from_snapshot(validated)

    assert restored is not validated
    assert restored.updated_at >= before_updated_at
    assert validated.updated_at == before_updated_at


def test_repository_classes_satisfy_transaction_protocols() -> None:
    """Concrete repositories implement the transaction Protocol surface."""
    from archium.application.visual.transaction_repository_protocols import (
        LayoutPlanRepositoryProtocol,
        PresentationRepositoryProtocol,
        VisualIntentRepositoryProtocol,
    )

    assert issubclass(VisualIntentRepository, VisualIntentRepositoryProtocol)
    assert issubclass(LayoutPlanRepository, LayoutPlanRepositoryProtocol)
    assert issubclass(PresentationRepository, PresentationRepositoryProtocol)
