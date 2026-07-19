"""Unit tests for TransactionExecutor safety guarantees."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from archium.application.visual.transaction_executor import TransactionExecutor
from archium.domain.visual.atomic_operation import (
    EnlargeHeroOperation,
    LockOperation,
    MoveOperation,
    ReduceTextOperation,
    UnlockOperation,
)
from archium.domain.visual.enums import LayoutElementRole, LayoutFamily, LayoutContentType
from archium.domain.visual.layout import LayoutElement, LayoutPlan
from archium.exceptions import WorkflowError


class _FakePlansRepo:
    def __init__(self, plan: LayoutPlan) -> None:
        self.plan = plan

    def get(self, plan_id):  # noqa: ANN001
        return self.plan if self.plan.id == plan_id else None

    def save(self, plan: LayoutPlan) -> LayoutPlan:
        self.plan = plan
        return plan


class _FakeIntentsRepo:
    def save(self, intent):  # noqa: ANN001
        return intent


class _FakePresentationsRepo:
    def __init__(self, slide) -> None:  # noqa: ANN001
        self.slide = slide

    def get_slide(self, slide_id):  # noqa: ANN001
        return self.slide if self.slide.id == slide_id else None


class _FakeHistory:
    def record_state(self, **kwargs):  # noqa: ANN003
        return None


class _FakeSession:
    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None


def _sample_plan(*, locked: bool = False) -> LayoutPlan:
    hero_id = str(uuid4())
    return LayoutPlan(
        id=uuid4(),
        slide_id=uuid4(),
        layout_family=LayoutFamily.DRAWING_FOCUS,
        layout_variant="default",
        page_width=720,
        page_height=540,
        design_system_id=uuid4(),
        visual_intent_id=uuid4(),
        hero_element_id=hero_id,
        elements=[
            LayoutElement(
                id=hero_id,
                role=LayoutElementRole.HERO_VISUAL,
                content_type=LayoutContentType.IMAGE,
                x=100,
                y=100,
                width=200,
                height=150,
                locked=locked,
            )
        ],
    )


def test_lock_missing_element_raises() -> None:
    plan = _sample_plan()
    slide = type("Slide", (), {"id": plan.slide_id, "layout_plan_id": plan.id, "visual_intent_id": None})()
    executor = TransactionExecutor(_FakeSession(), _FakeHistory())
    result = executor.execute_transaction(
        operations=[LockOperation(uuid4())],
        slide_id=slide.id,
        slide_snapshot=None,
        intents_repo=_FakeIntentsRepo(),
        plans_repo=_FakePlansRepo(plan),
        presentations_repo=_FakePresentationsRepo(slide),
    )
    assert result.success is False
    assert isinstance(result.error, WorkflowError)
    assert "未找到" in str(result.error)


def test_reduce_text_updates_element() -> None:
    caption_id = str(uuid4())
    plan = LayoutPlan(
        id=uuid4(),
        slide_id=uuid4(),
        layout_family=LayoutFamily.DRAWING_FOCUS,
        layout_variant="default",
        page_width=720,
        page_height=540,
        design_system_id=uuid4(),
        visual_intent_id=uuid4(),
        elements=[
            LayoutElement(
                id=caption_id,
                role=LayoutElementRole.CAPTION,
                content_type=LayoutContentType.TEXT,
                x=100,
                y=450,
                width=400,
                height=100,
                text_content="第一行说明\n第二行说明\n第三行说明",
            )
        ],
    )
    slide = type("Slide", (), {"id": plan.slide_id, "layout_plan_id": plan.id, "visual_intent_id": None})()
    repo = _FakePlansRepo(plan)
    executor = TransactionExecutor(_FakeSession(), _FakeHistory())
    result = executor.execute_transaction(
        operations=[ReduceTextOperation(UUID(caption_id), reduce_lines=2)],
        slide_id=slide.id,
        slide_snapshot=None,
        intents_repo=_FakeIntentsRepo(),
        plans_repo=repo,
        presentations_repo=_FakePresentationsRepo(slide),
    )
    assert result.success is True
    assert "第三行说明" not in (repo.plan.elements[0].text_content or "")
    assert "第一行说明" in (repo.plan.elements[0].text_content or "")


def test_move_element_to_right() -> None:
    caption_id = str(uuid4())
    plan = LayoutPlan(
        id=uuid4(),
        slide_id=uuid4(),
        layout_family=LayoutFamily.DRAWING_FOCUS,
        layout_variant="default",
        page_width=10,
        page_height=5.625,
        design_system_id=uuid4(),
        visual_intent_id=uuid4(),
        elements=[
            LayoutElement(
                id=caption_id,
                role=LayoutElementRole.CAPTION,
                content_type=LayoutContentType.TEXT,
                x=0.7,
                y=4.2,
                width=3.0,
                height=0.45,
                text_content="说明文字",
            )
        ],
    )
    slide = type("Slide", (), {"id": plan.slide_id, "layout_plan_id": plan.id, "visual_intent_id": None})()
    repo = _FakePlansRepo(plan)
    executor = TransactionExecutor(_FakeSession(), _FakeHistory())
    result = executor.execute_transaction(
        operations=[MoveOperation(UUID(caption_id), "right")],
        slide_id=slide.id,
        slide_snapshot=None,
        intents_repo=_FakeIntentsRepo(),
        plans_repo=repo,
        presentations_repo=_FakePresentationsRepo(slide),
    )
    assert result.success is True
    assert repo.plan.elements[0].x > 0.7


def test_reduce_text_missing_target_raises() -> None:
    plan = _sample_plan()
    slide = type("Slide", (), {"id": plan.slide_id, "layout_plan_id": plan.id, "visual_intent_id": None})()
    executor = TransactionExecutor(_FakeSession(), _FakeHistory())
    result = executor.execute_transaction(
        operations=[ReduceTextOperation(uuid4(), reduce_lines=2)],
        slide_id=slide.id,
        slide_snapshot=None,
        intents_repo=_FakeIntentsRepo(),
        plans_repo=_FakePlansRepo(plan),
        presentations_repo=_FakePresentationsRepo(slide),
    )
    assert result.success is False
    assert isinstance(result.error, WorkflowError)


def test_enlarge_locked_hero_raises() -> None:
    plan = _sample_plan(locked=True)
    slide = type("Slide", (), {"id": plan.slide_id, "layout_plan_id": plan.id, "visual_intent_id": None})()
    executor = TransactionExecutor(_FakeSession(), _FakeHistory())
    result = executor.execute_transaction(
        operations=[EnlargeHeroOperation(scale_factor=1.3)],
        slide_id=slide.id,
        slide_snapshot=None,
        intents_repo=_FakeIntentsRepo(),
        plans_repo=_FakePlansRepo(plan),
        presentations_repo=_FakePresentationsRepo(slide),
    )
    assert result.success is False
    assert isinstance(result.error, WorkflowError)


def test_lock_and_unlock_roundtrip() -> None:
    plan = _sample_plan()
    element_id = plan.elements[0].id
    slide = type("Slide", (), {"id": plan.slide_id, "layout_plan_id": plan.id, "visual_intent_id": None})()
    repo = _FakePlansRepo(plan)
    executor = TransactionExecutor(_FakeSession(), _FakeHistory())
    result = executor.execute_transaction(
        operations=[
            LockOperation(UUID(element_id)),
            UnlockOperation(UUID(element_id)),
        ],
        slide_id=slide.id,
        slide_snapshot=None,
        intents_repo=_FakeIntentsRepo(),
        plans_repo=repo,
        presentations_repo=_FakePresentationsRepo(slide),
    )
    assert result.success is True
    assert repo.plan.elements[0].locked is False
