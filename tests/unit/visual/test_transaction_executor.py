"""Unit tests for TransactionExecutor safety and operation coverage."""

from __future__ import annotations

from uuid import UUID, uuid4

from archium.application.visual.transaction_executor import (
    TransactionExecutionContext,
    TransactionExecutor,
)
from archium.domain.visual.atomic_operation import (
    AtomicOperation,
    EnlargeHeroOperation,
    IncreaseWhitespaceOperation,
    LockOperation,
    MoveOperation,
    OperationType,
    ReduceTextOperation,
    ResizeOperation,
    SwapOperation,
    UnlockOperation,
)
from archium.domain.visual.enums import LayoutContentType, LayoutElementRole, LayoutFamily
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
    def __init__(self) -> None:
        self.intent = None

    def get(self, intent_id):  # noqa: ANN001
        return self.intent

    def save(self, intent):  # noqa: ANN001
        self.intent = intent
        return intent


class _FakePresentationsRepo:
    def __init__(self, slide) -> None:  # noqa: ANN001
        self.slide = slide

    def get_slide(self, slide_id):  # noqa: ANN001
        return self.slide if self.slide.id == slide_id else None


class _FakeHistory:
    def __init__(self) -> None:
        self.records: list[str] = []

    def record_state(self, **kwargs):  # noqa: ANN003
        note = kwargs.get("note")
        if note:
            self.records.append(str(note))
        return None


class _TrackingSession:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


def _sample_plan(*, locked: bool = False, hero_id: str | None = None) -> LayoutPlan:
    resolved_hero = hero_id or str(uuid4())
    return LayoutPlan(
        id=uuid4(),
        slide_id=uuid4(),
        layout_family=LayoutFamily.DRAWING_FOCUS,
        layout_variant="default",
        page_width=720,
        page_height=540,
        design_system_id=uuid4(),
        visual_intent_id=uuid4(),
        hero_element_id=resolved_hero,
        whitespace_ratio=0.2,
        elements=[
            LayoutElement(
                id=resolved_hero,
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


def _two_element_plan() -> tuple[LayoutPlan, str, str]:
    first_id = str(uuid4())
    second_id = str(uuid4())
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
                id=first_id,
                role=LayoutElementRole.CAPTION,
                content_type=LayoutContentType.TEXT,
                x=1,
                y=4,
                width=3,
                height=0.5,
                text_content="左",
            ),
            LayoutElement(
                id=second_id,
                role=LayoutElementRole.BODY_TEXT,
                content_type=LayoutContentType.TEXT,
                x=6,
                y=4,
                width=3,
                height=0.5,
                text_content="右",
            ),
        ],
    )
    return plan, first_id, second_id


def _execute(
    *,
    plan: LayoutPlan,
    operations: list,
    execution_context: TransactionExecutionContext | None = None,
    slide=None,  # noqa: ANN001
) -> tuple[object, _FakePlansRepo]:
    slide_obj = slide or type(
        "Slide",
        (),
        {"id": plan.slide_id, "layout_plan_id": plan.id, "visual_intent_id": plan.visual_intent_id},
    )()
    repo = _FakePlansRepo(plan)
    executor = TransactionExecutor(_TrackingSession(), _FakeHistory())
    result = executor.execute_transaction(
        operations=operations,
        slide_id=slide_obj.id,
        slide_snapshot=None,
        intents_repo=_FakeIntentsRepo(),
        plans_repo=repo,
        presentations_repo=_FakePresentationsRepo(slide_obj),
        execution_context=execution_context,
    )
    return result, repo


def test_lock_missing_element_raises() -> None:
    plan = _sample_plan()
    result, _ = _execute(plan=plan, operations=[LockOperation(uuid4())])
    assert result.success is False
    assert isinstance(result.error, WorkflowError)
    assert "未找到" in str(result.error)


def test_slide_not_found() -> None:
    plan = _sample_plan()
    executor = TransactionExecutor(_TrackingSession(), _FakeHistory())
    result = executor.execute_transaction(
        operations=[IncreaseWhitespaceOperation()],
        slide_id=uuid4(),
        slide_snapshot=None,
        intents_repo=_FakeIntentsRepo(),
        plans_repo=_FakePlansRepo(plan),
        presentations_repo=_FakePresentationsRepo(
            type("Slide", (), {"id": plan.slide_id, "layout_plan_id": plan.id, "visual_intent_id": None})()
        ),
    )
    assert result.success is False
    assert isinstance(result.error, WorkflowError)


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
    result, repo = _execute(
        plan=plan,
        operations=[ReduceTextOperation(UUID(caption_id), reduce_lines=2)],
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
    result, repo = _execute(plan=plan, operations=[MoveOperation(UUID(caption_id), "right")])
    assert result.success is True
    assert repo.plan.elements[0].x > 0.7


def test_swap_elements_exchanges_geometry() -> None:
    plan, first_id, second_id = _two_element_plan()
    first_before = plan.element_by_id(first_id)
    second_before = plan.element_by_id(second_id)
    assert first_before is not None and second_before is not None
    result, repo = _execute(
        plan=plan,
        operations=[SwapOperation(first_id, second_id)],
    )
    assert result.success is True
    first_after = repo.plan.element_by_id(first_id)
    second_after = repo.plan.element_by_id(second_id)
    assert first_after is not None and second_after is not None
    assert first_after.x == second_before.x
    assert second_after.x == first_before.x


def test_increase_whitespace_shrinks_unlocked_elements() -> None:
    hero_id = str(uuid4())
    plan = _sample_plan(hero_id=hero_id)
    hero_before = plan.element_by_id(hero_id)
    assert hero_before is not None
    result, repo = _execute(plan=plan, operations=[IncreaseWhitespaceOperation()])
    assert result.success is True
    hero_after = repo.plan.element_by_id(hero_id)
    assert hero_after is not None
    assert hero_after.width < hero_before.width


def test_enlarge_hero_success() -> None:
    hero_id = str(uuid4())
    plan = _sample_plan(hero_id=hero_id)
    hero_before = plan.element_by_id(hero_id)
    assert hero_before is not None
    result, repo = _execute(plan=plan, operations=[EnlargeHeroOperation(scale_factor=1.2)])
    assert result.success is True
    hero_after = repo.plan.element_by_id(hero_id)
    assert hero_after is not None
    assert hero_after.width > hero_before.width


def test_enlarge_locked_hero_raises() -> None:
    plan = _sample_plan(locked=True)
    result, _ = _execute(plan=plan, operations=[EnlargeHeroOperation(scale_factor=1.3)])
    assert result.success is False
    assert isinstance(result.error, WorkflowError)


def test_resize_element_scales_geometry() -> None:
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
                x=1,
                y=4,
                width=2,
                height=0.5,
                text_content="说明",
            )
        ],
    )
    before = plan.element_by_id(caption_id)
    assert before is not None
    result, repo = _execute(
        plan=plan,
        operations=[ResizeOperation(caption_id, scale_factor=1.5)],
    )
    assert result.success is True
    after = repo.plan.element_by_id(caption_id)
    assert after is not None
    assert after.width > before.width


def test_update_element_text() -> None:
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
                x=1,
                y=4,
                width=2,
                height=0.5,
                text_content="旧文案",
            )
        ],
    )
    result, repo = _execute(
        plan=plan,
        operations=[
            AtomicOperation(
                operation_type=OperationType.UPDATE_ELEMENT_TEXT,
                target_element_id=caption_id,
                params={"text": "新文案"},
            )
        ],
    )
    assert result.success is True
    assert repo.plan.elements[0].text_content == "新文案"


def test_validation_failure_rolls_back_layout() -> None:
    hero_id = str(uuid4())
    plan = _sample_plan(hero_id=hero_id)
    hero_before = plan.element_by_id(hero_id)
    assert hero_before is not None
    original_width = hero_before.width

    def _reject(_: LayoutPlan) -> None:
        raise WorkflowError("layout invalid")

    context = TransactionExecutionContext(
        replan_layout_change=lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError()),
        validate_layout=_reject,
    )
    result, repo = _execute(
        plan=plan,
        operations=[IncreaseWhitespaceOperation()],
        execution_context=context,
    )
    assert result.success is False
    hero_after = repo.plan.element_by_id(hero_id)
    assert hero_after is not None
    assert hero_after.width == original_width


def test_swap_missing_element_raises() -> None:
    plan, first_id, _second_id = _two_element_plan()
    result, _ = _execute(
        plan=plan,
        operations=[SwapOperation(first_id, str(uuid4()))],
    )
    assert result.success is False
    assert isinstance(result.error, WorkflowError)


def test_move_missing_element_raises() -> None:
    plan = _sample_plan()
    result, _ = _execute(plan=plan, operations=[MoveOperation(uuid4(), "right")])
    assert result.success is False
    assert isinstance(result.error, WorkflowError)


def test_lock_without_layout_plan_raises() -> None:
    plan = _sample_plan()
    slide = type(
        "Slide",
        (),
        {"id": plan.slide_id, "layout_plan_id": None, "visual_intent_id": None},
    )()

    class _EmptyPlansRepo:
        def get(self, _plan_id):  # noqa: ANN001
            return None

        def save(self, plan: LayoutPlan) -> LayoutPlan:
            return plan

    executor = TransactionExecutor(_TrackingSession(), _FakeHistory())
    result = executor.execute_transaction(
        operations=[LockOperation(UUID(plan.elements[0].id))],
        slide_id=slide.id,
        slide_snapshot=None,
        intents_repo=_FakeIntentsRepo(),
        plans_repo=_EmptyPlansRepo(),
        presentations_repo=_FakePresentationsRepo(slide),
    )
    assert result.success is False
    assert isinstance(result.error, WorkflowError)


def test_resize_invalid_scale_raises() -> None:
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
                x=1,
                y=4,
                width=2,
                height=0.5,
                text_content="说明",
            )
        ],
    )
    result, _ = _execute(
        plan=plan,
        operations=[ResizeOperation(caption_id, scale_factor=0)],
    )
    assert result.success is False
    assert isinstance(result.error, WorkflowError)


def test_empty_operation_list_commits_successfully() -> None:
    plan = _sample_plan()
    result, _ = _execute(plan=plan, operations=[])
    assert result.success is True
    assert result.executed_operations == []


def test_lock_and_unlock_roundtrip() -> None:
    plan = _sample_plan()
    element_id = plan.elements[0].id
    result, repo = _execute(
        plan=plan,
        operations=[
            LockOperation(UUID(element_id)),
            UnlockOperation(UUID(element_id)),
        ],
    )
    assert result.success is True
    assert repo.plan.elements[0].locked is False


def test_successful_transaction_records_history() -> None:
    plan = _sample_plan()
    history = _FakeHistory()
    slide = type(
        "Slide",
        (),
        {"id": plan.slide_id, "layout_plan_id": plan.id, "visual_intent_id": plan.visual_intent_id},
    )()
    executor = TransactionExecutor(_TrackingSession(), history)
    result = executor.execute_transaction(
        operations=[IncreaseWhitespaceOperation()],
        slide_id=slide.id,
        slide_snapshot=None,
        intents_repo=_FakeIntentsRepo(),
        plans_repo=_FakePlansRepo(plan),
        presentations_repo=_FakePresentationsRepo(slide),
    )
    assert result.success is True
    assert history.records
