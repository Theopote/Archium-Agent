"""DB integration tests for composite visual edit transactions."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest
from archium.application.visual.layout_validation_service import LayoutValidationService
from archium.application.visual.operation_decomposer import OperationDecomposer
from archium.application.visual.transaction_executor import TransactionExecutor
from archium.application.visual.visual_edit_service import VisualEditService
from archium.application.visual.visual_history_service import VisualHistoryService
from archium.domain.citation import Citation
from archium.domain.enums import ApprovalStatus, SlideType, VisualType
from archium.domain.presentation import Presentation, PresentationBrief, Storyline
from archium.domain.project import Project
from archium.domain.slide import SlideSpec, VisualRequirement
from archium.domain.visual.atomic_operation import ReduceTextOperation, SwapOperation
from archium.domain.visual.defaults import default_presentation_design_system
from archium.domain.visual.design_system import DesignSystem
from archium.domain.visual.edit_intent import VisualEditIntent
from archium.domain.visual.enums import (
    LayoutContentType,
    LayoutElementRole,
    LayoutFamily,
    VisualContentType,
)
from archium.domain.visual.layout import LayoutElement, LayoutPlan
from archium.domain.visual.nlp_parser import Modifier, ModifierType, ParsedIntent
from archium.domain.visual.slide_edit_snapshot import SlideEditSnapshot
from archium.domain.visual.visual_intent import VisualIntent
from archium.infrastructure.database.repositories import PresentationRepository, ProjectRepository
from archium.infrastructure.database.visual_repositories import (
    DesignSystemRepository,
    LayoutPlanRepository,
    VisualIntentRepository,
)
from archium.infrastructure.layout.generators.base import (
    LayoutContentBundle,
    LayoutGeneratorContext,
)
from archium.infrastructure.layout.layout_solver import LayoutSolver
from sqlalchemy.orm import Session

CAPTION_TEXT = "总平面确立院落轴线与核心公服节点，并串联开放空间与慢行系统。"


@dataclass(frozen=True)
class DrawingFocusFixture:
    slide: SlideSpec
    layout_plan: LayoutPlan
    visual_intent: VisualIntent
    design: DesignSystem
    hero_element_id: str
    caption_element_id: str


def _validate_plan(plan: LayoutPlan, design: DesignSystem) -> None:
    report = LayoutValidationService().validate(
        plan,
        design,
        require_source=True,
        drawing_hero=plan.layout_family == LayoutFamily.DRAWING_FOCUS,
    )
    assert report.valid, [issue.message for issue in report.issues]


def _reload_plan(db_session: Session, slide: SlideSpec) -> LayoutPlan:
    assert slide.layout_plan_id is not None
    plan = LayoutPlanRepository(db_session).get(slide.layout_plan_id)
    assert plan is not None
    return plan


def _reload_slide(db_session: Session, slide_id: UUID) -> SlideSpec:
    slide = PresentationRepository(db_session).get_slide(slide_id)
    assert slide is not None
    return slide


def _build_valid_drawing_focus_plan(
    *,
    slide: SlideSpec,
    intent: VisualIntent,
    design: DesignSystem,
) -> LayoutPlan:
    plan = LayoutSolver().generate(
        LayoutFamily.DRAWING_FOCUS,
        LayoutGeneratorContext(
            slide=slide,
            visual_intent=intent,
            art_direction=None,
            design_system=design,
            content=LayoutContentBundle(
                title=slide.title,
                message=CAPTION_TEXT,
                captions=[CAPTION_TEXT],
                source_text="来源：测试任务书",
                hero_asset_ref="assets/site-plan.png",
            ),
            variant="full_canvas",
        ),
    )
    return plan.model_copy(
        update={
            "slide_id": slide.id,
            "design_system_id": design.id,
            "visual_intent_id": intent.id,
        }
    )


@pytest.fixture
def drawing_focus_slide(db_session: Session) -> DrawingFocusFixture:
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
            message=CAPTION_TEXT,
            slide_type=SlideType.CONTENT,
            visual_requirements=[
                VisualRequirement(
                    type=VisualType.SITE_PLAN,
                    description="总平面图",
                    preferred_asset_ids=[uuid4()],
                )
            ],
            source_citations=[
                Citation(
                    document_id=uuid4(),
                    document_name="任务书.pdf",
                    page_number=1,
                )
            ],
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
    plan = _build_valid_drawing_focus_plan(slide=slide, intent=intent, design=design)
    unlocked_elements = [
        element.model_copy(update={"locked": False}) if element.id == "hero" else element
        for element in plan.elements
    ]
    plan = plan.model_copy(update={"elements": unlocked_elements})
    _validate_plan(plan, design)
    saved_plan = LayoutPlanRepository(db_session).save(plan)
    slide.visual_intent_id = intent.id
    slide.layout_plan_id = saved_plan.id
    presentations.save_slide(slide)
    db_session.commit()

    hero = next(
        element
        for element in saved_plan.elements
        if element.role == LayoutElementRole.HERO_VISUAL
    )
    caption = next(
        element
        for element in saved_plan.elements
        if element.role == LayoutElementRole.CAPTION
    )
    return DrawingFocusFixture(
        slide=slide,
        layout_plan=saved_plan,
        visual_intent=intent,
        design=design,
        hero_element_id=hero.id,
        caption_element_id=caption.id,
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
            "reduce_lines": 1,
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


def test_fixture_plan_is_valid_under_design_system(
    drawing_focus_slide: DrawingFocusFixture,
) -> None:
    _validate_plan(drawing_focus_slide.layout_plan, drawing_focus_slide.design)


def test_composite_transaction_commits_with_design_validation(
    db_session: Session,
    drawing_focus_slide: DrawingFocusFixture,
) -> None:
    service = VisualEditService(db_session)
    baseline = drawing_focus_slide.layout_plan
    baseline_caption = baseline.element_by_id(drawing_focus_slide.caption_element_id)
    assert baseline_caption is not None

    result = service._apply_composite_operation(
        drawing_focus_slide.slide.id,
        _full_composite_intent(),
        candidate_count=1,
    )

    assert "复合操作" in result.message
    assert result.validation is not None
    assert result.validation.valid is True

    slide = _reload_slide(db_session, drawing_focus_slide.slide.id)
    plan = _reload_plan(db_session, slide)
    _validate_plan(plan, drawing_focus_slide.design)

    drawing = plan.element_by_id(drawing_focus_slide.hero_element_id)
    caption = plan.element_by_id(drawing_focus_slide.caption_element_id)
    assert drawing is not None and caption is not None
    assert drawing.locked is True
    assert drawing.x == baseline.element_by_id(drawing_focus_slide.hero_element_id).x
    assert drawing.y == baseline.element_by_id(drawing_focus_slide.hero_element_id).y
    assert caption.x > baseline_caption.x
    assert len(caption.text_content or "") < len(baseline_caption.text_content or "")


def test_composite_transaction_rolls_back_on_failure_with_design_validation(
    db_session: Session,
    drawing_focus_slide: DrawingFocusFixture,
) -> None:
    fixture = drawing_focus_slide
    slide = _reload_slide(db_session, fixture.slide.id)
    baseline = _reload_plan(db_session, slide)
    _validate_plan(baseline, fixture.design)
    service = VisualEditService(db_session)

    decomposer = OperationDecomposer()
    snapshot = SlideEditSnapshot(
        slide_id=slide.id,
        presentation_id=slide.presentation_id,
        visual_intent=fixture.visual_intent,
        layout_plan=baseline,
    )
    operations = decomposer.decompose(_full_composite_intent(), snapshot)
    failing_ops = operations + [ReduceTextOperation(uuid4(), reduce_lines=1)]
    execution_context = service._build_transaction_execution_context(slide, candidate_count=1)
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
    _validate_plan(restored, fixture.design)
    drawing = restored.element_by_id(fixture.hero_element_id)
    caption = restored.element_by_id(fixture.caption_element_id)
    baseline_caption = baseline.element_by_id(fixture.caption_element_id)
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
    snapshot = SlideEditSnapshot(
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

        def flush(self) -> None:
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
