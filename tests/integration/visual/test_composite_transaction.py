"""DB integration tests for composite visual edit transactions."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest
from archium.application.visual.operation_decomposer import OperationDecomposer
from archium.application.visual.transaction_executor import TransactionExecutor
from archium.application.visual.visual_edit_service import VisualEditService
from archium.application.visual.visual_history_service import VisualHistoryService
from archium.domain.enums import ApprovalStatus, SlideType
from archium.domain.presentation import Presentation, PresentationBrief, Storyline
from archium.domain.project import Project
from archium.domain.slide import SlideSpec
from archium.domain.visual.defaults import default_presentation_design_system
from archium.domain.visual.edit_intent import VisualEditIntent
from archium.domain.visual.enums import (
    LayoutContentType,
    LayoutElementRole,
    LayoutFamily,
    VisualContentType,
)
from archium.domain.visual.layout import LayoutElement, LayoutPlan
from archium.domain.visual.nlp_parser import Modifier, ModifierType, ParsedIntent
from archium.domain.visual.slide import SlideSnapshot
from archium.domain.visual.visual_intent import VisualIntent
from archium.domain.visual.atomic_operation import ReduceTextOperation, SwapOperation
from archium.infrastructure.database.repositories import PresentationRepository, ProjectRepository
from archium.infrastructure.database.visual_repositories import (
    DesignSystemRepository,
    LayoutPlanRepository,
    VisualIntentRepository,
)
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class DrawingFocusFixture:
    slide: SlideSpec
    layout_plan: LayoutPlan
    visual_intent: VisualIntent
    drawing_id: UUID
    caption_id: UUID


def _reload_plan(db_session: Session, slide: SlideSpec) -> LayoutPlan:
    assert slide.layout_plan_id is not None
    plan = LayoutPlanRepository(db_session).get(slide.layout_plan_id)
    assert plan is not None
    return plan


def _reload_slide(db_session: Session, slide_id: UUID) -> SlideSpec:
    slide = PresentationRepository(db_session).get_slide(slide_id)
    assert slide is not None
    return slide


@pytest.fixture
def drawing_focus_slide(db_session: Session) -> DrawingFocusFixture:
    drawing_id = uuid4()
    caption_id = uuid4()
    project = ProjectRepository(db_session).create(Project(name="Composite transaction"))
    presentations = PresentationRepository(db_session)
    presentation = presentations.create_presentation(
        Presentation(project_id=project.id, title="Composite Deck")
    )
    brief = presentations.save_brief(
        PresentationBrief(
            project_id=project.id,
            presentation_id=presentation.id,
            title="Composite Deck",
            audience="甲方",
            purpose="复合操作集成测试",
            core_message="锁定图纸并移动说明。",
            approval_status=ApprovalStatus.APPROVED,
        )
    )
    storyline = presentations.save_storyline(
        Storyline(
            presentation_id=presentation.id,
            thesis="复合事务应原子提交或完整回滚。",
            approval_status=ApprovalStatus.APPROVED,
        )
    )
    presentation.current_brief_id = brief.id
    presentation.current_storyline_id = storyline.id
    presentations.update_presentation(presentation)

    design = DesignSystemRepository(db_session).save(default_presentation_design_system())
    slide = presentations.save_slide(
        SlideSpec(
            presentation_id=presentation.id,
            chapter_id="ch1",
            order=0,
            title="图纸焦点页",
            message="第一行说明\n第二行说明\n第三行说明",
            slide_type=SlideType.CONTENT,
        )
    )
    intent = VisualIntentRepository(db_session).save(
        VisualIntent(
            slide_id=slide.id,
            presentation_id=presentation.id,
            communication_goal="展示图纸与说明",
            audience_takeaway=slide.message,
            visual_priority="drawing > caption",
            dominant_content_type=VisualContentType.SITE_PLAN,
            preferred_layout_families=[LayoutFamily.DRAWING_FOCUS],
        )
    )
    raw_plan = LayoutPlan(
        slide_id=slide.id,
        layout_family=LayoutFamily.DRAWING_FOCUS,
        layout_variant="default",
        page_width=10,
        page_height=5.625,
        hero_element_id=str(drawing_id),
        reading_order=[str(drawing_id), str(caption_id)],
        elements=[
            LayoutElement(
                id=str(drawing_id),
                role=LayoutElementRole.HERO_VISUAL,
                content_type=LayoutContentType.DRAWING,
                content_ref="assets/site-plan.png",
                x=0.7,
                y=1.0,
                width=3.5,
                height=2.5,
            ),
            LayoutElement(
                id=str(caption_id),
                role=LayoutElementRole.CAPTION,
                content_type=LayoutContentType.TEXT,
                text_content="第一行说明\n第二行说明\n第三行说明",
                x=0.7,
                y=4.2,
                width=3.0,
                height=0.45,
            ),
        ],
        design_system_id=design.id,
        visual_intent_id=intent.id,
    )
    plan = LayoutPlanRepository(db_session).save(raw_plan)
    slide.visual_intent_id = intent.id
    slide.layout_plan_id = plan.id
    presentations.save_slide(slide)
    db_session.commit()
    return DrawingFocusFixture(
        slide=slide,
        layout_plan=plan,
        visual_intent=intent,
        drawing_id=drawing_id,
        caption_id=caption_id,
    )


def _full_composite_intent() -> ParsedIntent:
    return ParsedIntent(
        intent=VisualEditIntent.CHANGE_LAYOUT,
        params={
            "target": "说明",
            "position": "右边",
            "multi_step_operations": [
                {"operation": "move_to", "targets": ["说明", "右边"]},
            ],
            "reduce_lines": 2,
            "reduce_text_element": "说明",
        },
        modifiers=[
            Modifier(
                type=ModifierType.CONSTRAINT,
                target="图纸",
                value="preserve",
                description="约束: 保持图纸不动",
            ),
            Modifier(
                type=ModifierType.MULTI_STEP,
                value={"operation": "move_to", "targets": ["说明", "右边"]},
                description="位置操作: move_to",
            ),
        ],
        confidence=0.85,
    )


def test_composite_transaction_commits_in_database(
    db_session: Session,
    drawing_focus_slide: DrawingFocusFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = VisualEditService(db_session)
    baseline = drawing_focus_slide.layout_plan
    original_builder = service._build_transaction_execution_context

    def _context_without_blocking_validation(slide: object, *, candidate_count: int):
        context = original_builder(slide, candidate_count=candidate_count)
        from archium.application.visual.transaction_executor import TransactionExecutionContext

        return TransactionExecutionContext(
            replan_layout_change=context.replan_layout_change,
            validate_layout=lambda _plan: None,
            replan_current_intent=context.replan_current_intent,
            resolve_asset_ref=context.resolve_asset_ref,
        )

    monkeypatch.setattr(service, "_build_transaction_execution_context", _context_without_blocking_validation)

    result = service._apply_composite_operation(
        drawing_focus_slide.slide.id,
        _full_composite_intent(),
        candidate_count=1,
    )

    assert "复合操作" in result.message
    slide = _reload_slide(db_session, drawing_focus_slide.slide.id)
    plan = _reload_plan(db_session, slide)
    drawing = plan.element_by_id(str(drawing_focus_slide.drawing_id))
    caption = plan.element_by_id(str(drawing_focus_slide.caption_id))
    assert drawing is not None and caption is not None
    assert drawing.locked is True
    assert drawing.x == baseline.elements[0].x
    assert drawing.y == baseline.elements[0].y
    assert caption.x > baseline.element_by_id(str(drawing_focus_slide.caption_id)).x
    assert "第三行说明" not in (caption.text_content or "")


def test_composite_transaction_rolls_back_on_failure(
    db_session: Session,
    drawing_focus_slide: DrawingFocusFixture,
) -> None:
    fixture = drawing_focus_slide
    slide = _reload_slide(db_session, fixture.slide.id)
    baseline = _reload_plan(db_session, slide)
    service = VisualEditService(db_session)

    decomposer = OperationDecomposer()
    snapshot = SlideSnapshot(
        slide_id=slide.id,
        presentation_id=slide.presentation_id,
        visual_intent=fixture.visual_intent,
        layout_plan=baseline,
    )
    operations = decomposer.decompose(_full_composite_intent(), snapshot)
    failing_ops = operations + [ReduceTextOperation(uuid4(), reduce_lines=1)]
    execution_context = service._build_transaction_execution_context(slide, candidate_count=1)
    from archium.application.visual.transaction_executor import TransactionExecutionContext

    execution_context = TransactionExecutionContext(
        replan_layout_change=execution_context.replan_layout_change,
        validate_layout=lambda _plan: None,
        replan_current_intent=execution_context.replan_current_intent,
        resolve_asset_ref=execution_context.resolve_asset_ref,
    )
    executor = TransactionExecutor(db_session, VisualHistoryService(db_session))
    tx_result = executor.execute_transaction(
        operations=failing_ops,
        slide_id=slide.id,
        slide_snapshot=snapshot,
        intents_repo=VisualIntentRepository(db_session),
        plans_repo=LayoutPlanRepository(db_session),
        presentations_repo=PresentationRepository(db_session),
        execution_context=execution_context,
    )

    assert tx_result.success is False
    restored = _reload_plan(db_session, slide)
    drawing = restored.element_by_id(str(fixture.drawing_id))
    caption = restored.element_by_id(str(fixture.caption_id))
    baseline_caption = baseline.element_by_id(str(fixture.caption_id))
    assert drawing is not None and caption is not None and baseline_caption is not None
    assert drawing.locked is False
    assert caption.x == baseline_caption.x
    assert caption.text_content == baseline_caption.text_content


def test_swap_operation_exchanges_element_positions() -> None:
    left_id = uuid4()
    right_id = uuid4()
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
                id=str(left_id),
                role=LayoutElementRole.CAPTION,
                content_type=LayoutContentType.TEXT,
                text_content="左",
                x=80,
                y=200,
                width=120,
                height=60,
            ),
            LayoutElement(
                id=str(right_id),
                role=LayoutElementRole.BODY_TEXT,
                content_type=LayoutContentType.TEXT,
                text_content="右",
                x=480,
                y=260,
                width=120,
                height=60,
            ),
        ],
    )
    snapshot = SlideSnapshot(
        slide_id=plan.slide_id,
        presentation_id=uuid4(),
        visual_intent=None,
        layout_plan=plan,
    )
    parsed = ParsedIntent(
        intent=VisualEditIntent.CHANGE_LAYOUT,
        params={
            "multi_step_operations": [
                {"operation": "swap", "targets": [str(left_id), str(right_id)]},
            ],
        },
        modifiers=[],
        confidence=0.9,
    )
    operations = OperationDecomposer().decompose(parsed, snapshot)
    assert len(operations) == 1
    assert isinstance(operations[0], SwapOperation)

    slide = type(
        "Slide",
        (),
        {"id": plan.slide_id, "layout_plan_id": plan.id, "visual_intent_id": None},
    )()

    class _Plans:
        def __init__(self, current: LayoutPlan) -> None:
            self.current = current

        def get(self, plan_id: UUID) -> LayoutPlan | None:
            return self.current if self.current.id == plan_id else None

        def save(self, updated: LayoutPlan) -> LayoutPlan:
            self.current = updated
            return updated

    class _Session:
        def commit(self) -> None:
            return None

        def rollback(self) -> None:
            return None

    plans = _Plans(plan)
    executor = TransactionExecutor(_Session(), type("H", (), {"record_state": lambda *a, **k: None})())  # type: ignore[arg-type]
    result = executor.execute_transaction(
        operations=operations,
        slide_id=slide.id,
        slide_snapshot=snapshot,
        intents_repo=type("R", (), {"save": lambda self, x: x})(),
        plans_repo=plans,
        presentations_repo=type("R", (), {"get_slide": lambda self, sid: slide if sid == slide.id else None})(),
    )
    assert result.success is True
    left = plans.current.element_by_id(str(left_id))
    right = plans.current.element_by_id(str(right_id))
    assert left is not None and right is not None
    assert left.x == 480
    assert left.y == 260
    assert right.x == 80
    assert right.y == 200
