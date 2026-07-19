"""End-to-end integration: locked hero survives Studio visual workflow."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

import pytest
from archium.application.content_adaptation_service import ContentAdaptationService
from archium.application.visual.layout_repair_service import LayoutRepairService
from archium.application.visual.layout_validation_service import LayoutValidationService
from archium.application.visual.visual_edit_service import VisualEditService
from archium.domain.content_adaptation import ContentAdaptationAction
from archium.domain.enums import ApprovalStatus, SlideType
from archium.domain.presentation import Presentation, PresentationBrief, Storyline
from archium.domain.project import Project
from archium.domain.slide import SlideSpec
from archium.domain.visual.defaults import default_presentation_design_system
from archium.domain.visual.edit_intent import VisualEditIntent
from archium.domain.visual.enums import LayoutContentType, LayoutElementRole, LayoutFamily
from archium.domain.visual.layout import LayoutElement, LayoutPlan
from archium.domain.visual.slide_edit_command import SlideEditCommand, SlideEditScope
from archium.infrastructure.database.repositories import PresentationRepository, ProjectRepository
from archium.infrastructure.database.visual_repositories import (
    DesignSystemRepository,
    LayoutPlanRepository,
)
from archium.infrastructure.renderers.pptxgen.layout_plan_adapter import PptxLayoutPlanAdapter
from archium.ui.studio_service import apply_slide_edit_command
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class HeroFingerprint:
    content_ref: str | None
    x: float
    y: float
    width: float
    height: float
    locked: bool


def _hero_fingerprint(plan: LayoutPlan) -> HeroFingerprint:
    hero = plan.element_by_id("hero")
    assert hero is not None
    return HeroFingerprint(
        content_ref=hero.content_ref,
        x=round(hero.x, 4),
        y=round(hero.y, 4),
        width=round(hero.width, 4),
        height=round(hero.height, 4),
        locked=hero.locked,
    )


def _load_slide_plan(db_session: Session, slide: SlideSpec) -> LayoutPlan:
    plans = LayoutPlanRepository(db_session)
    assert slide.layout_plan_id is not None
    plan = plans.get(slide.layout_plan_id)
    assert plan is not None
    return plan


def _reload_slide(db_session: Session, slide_id) -> SlideSpec:
    slide = PresentationRepository(db_session).get_slide(slide_id)
    assert slide is not None
    return slide


def _repair_and_persist(db_session: Session, slide: SlideSpec, plan: LayoutPlan) -> LayoutPlan:
    design_repo = DesignSystemRepository(db_session)
    design = design_repo.get(plan.design_system_id)
    if design is None:
        design = design_repo.save(default_presentation_design_system())

    report = LayoutValidationService().validate(
        plan,
        design,
        require_source=False,
        drawing_hero=plan.layout_family == LayoutFamily.DRAWING_FOCUS,
    )
    if not any(issue.auto_repairable for issue in report.issues):
        return plan

    repaired = LayoutRepairService().repair(plan, report, design).plan
    saved = LayoutPlanRepository(db_session).save(repaired)
    slide.layout_plan_id = saved.id
    PresentationRepository(db_session).save_slide(slide)
    db_session.commit()
    return saved


def _render_hero(plan: LayoutPlan, design) -> dict[str, object]:
    instruction = PptxLayoutPlanAdapter().render_slide(plan, design)
    hero = next(item for item in instruction.elements if item["id"] == "hero")
    return hero


@pytest.fixture
def locked_hero_slide(db_session: Session) -> tuple[Presentation, SlideSpec, HeroFingerprint]:
    project = ProjectRepository(db_session).create(Project(name="Locked hero workflow"))
    presentations = PresentationRepository(db_session)
    presentation = presentations.create_presentation(
        Presentation(project_id=project.id, title="Locked Hero Deck")
    )
    brief = presentations.save_brief(
        PresentationBrief(
            project_id=project.id,
            presentation_id=presentation.id,
            title="Locked Hero Deck",
            audience="甲方",
            purpose="集成测试",
            core_message="锁定主图跨服务工作流验收。",
            approval_status=ApprovalStatus.APPROVED,
        )
    )
    storyline = presentations.save_storyline(
        Storyline(
            presentation_id=presentation.id,
            thesis="锁定主图不应被重排或修复改写。",
            approval_status=ApprovalStatus.APPROVED,
        )
    )
    presentation.current_brief_id = brief.id
    presentation.current_storyline_id = storyline.id
    presentations.update_presentation(presentation)

    design = DesignSystemRepository(db_session).save(default_presentation_design_system())
    hero_ref = str(uuid4())
    slide = presentations.save_slide(
        SlideSpec(
            presentation_id=presentation.id,
            chapter_id="ch1",
            order=0,
            title="主图锁定页",
            message=(
                "本页核心结论：锁定主图在换版式、内容适配与自动修复后仍保持不变；"
                "第二句补充空间策略；第三句补充实施路径。"
            ),
            slide_type=SlideType.CONTENT,
        )
    )
    plan = LayoutPlan(
        slide_id=slide.id,
        layout_family=LayoutFamily.HERO,
        layout_variant="split",
        page_width=10,
        page_height=5.625,
        hero_element_id="hero",
        reading_order=["title", "hero", "body"],
        whitespace_ratio=0.3,
        elements=[
            LayoutElement(
                id="title",
                role=LayoutElementRole.TITLE,
                content_type=LayoutContentType.TEXT,
                text_content="主图锁定页",
                x=0.7,
                y=0.45,
                width=8.6,
                height=0.55,
                style_token="title",
            ),
            LayoutElement(
                id="hero",
                role=LayoutElementRole.HERO_VISUAL,
                content_type=LayoutContentType.IMAGE,
                content_ref=hero_ref,
                x=1.2,
                y=1.5,
                width=7.5,
                height=3.2,
            ),
            LayoutElement(
                id="body",
                role=LayoutElementRole.BODY_TEXT,
                content_type=LayoutContentType.TEXT,
                text_content="正文区域会在重排时被重新布局。",
                x=1.0,
                y=4.9,
                width=8.0,
                height=0.55,
                style_token="body",
            ),
        ],
        design_system_id=design.id,
        visual_intent_id=uuid4(),
    )
    saved_plan = LayoutPlanRepository(db_session).save(plan)
    slide.layout_plan_id = saved_plan.id
    presentations.save_slide(slide)
    db_session.commit()

    apply_slide_edit_command(
        db_session,
        SlideEditCommand(
            slide_id=slide.id,
            scope=SlideEditScope.VISUAL,
            action=VisualEditIntent.LOCK_ELEMENT.value,
            params={"element_id": "hero"},
        ),
    )
    db_session.commit()

    locked_slide = _reload_slide(db_session, slide.id)
    baseline = _hero_fingerprint(_load_slide_plan(db_session, locked_slide))
    assert baseline.locked is True
    assert baseline.content_ref == hero_ref
    return presentation, locked_slide, baseline


def test_locked_hero_survives_studio_visual_workflow(
    db_session: Session,
    locked_hero_slide: tuple[Presentation, SlideSpec, HeroFingerprint],
) -> None:
    """Lock hero → change layout → content adaptation → repair → render keeps hero intact."""
    _presentation, slide, baseline = locked_hero_slide
    visual = VisualEditService(db_session)

    change_layout = visual.apply_text(slide.id, "换一种版式")
    assert change_layout.layout_plan is not None
    slide = _reload_slide(db_session, slide.id)
    assert _hero_fingerprint(_load_slide_plan(db_session, slide)) == baseline

    content = ContentAdaptationService(db_session)
    content.apply(slide.id, ContentAdaptationAction.SHORTEN, replan_visual=True)
    slide = _reload_slide(db_session, slide.id)
    plan = _load_slide_plan(db_session, slide)
    assert _hero_fingerprint(plan) == baseline

    plan = _repair_and_persist(db_session, slide, plan)
    slide = _reload_slide(db_session, slide.id)
    assert _hero_fingerprint(plan) == baseline

    design = DesignSystemRepository(db_session).get(plan.design_system_id)
    assert design is not None
    rendered_hero = _render_hero(plan, design)
    assert rendered_hero["content_ref"] == baseline.content_ref
    assert round(rendered_hero["x"], 4) == baseline.x
    assert round(rendered_hero["y"], 4) == baseline.y
    assert round(rendered_hero["w"], 4) == baseline.width
    assert round(rendered_hero["h"], 4) == baseline.height

    # Unlocked elements may move during replan — hero must not.
    assert plan.element_by_id("hero") is not None
    assert plan.element_by_id("hero").locked is True


def test_safe_fallback_merge_preserves_locked_hero(
    db_session: Session,
    locked_hero_slide: tuple[Presentation, SlideSpec, HeroFingerprint],
) -> None:
    """Safe fallback uses preserve_locked_elements — locked hero must survive candidate swap."""
    from archium.application.visual.layout_locked import preserve_locked_elements

    _presentation, slide, baseline = locked_hero_slide
    current = _load_slide_plan(db_session, slide)
    alternate = current.model_copy(
        update={
            "layout_variant": "alternate_fallback",
            "version": current.version + 1,
            "elements": [
                element.model_copy(
                    update={
                        "x": 9.0,
                        "y": 9.0,
                        "width": 0.5,
                        "height": 0.5,
                        "content_ref": "assets/replaced.png",
                        "locked": False,
                    }
                )
                if element.id == "hero"
                else element.model_copy(update={"x": element.x + 0.5})
                for element in current.elements
            ],
        }
    )
    merged = preserve_locked_elements(alternate, current)
    assert _hero_fingerprint(merged) == baseline


def test_pick_safe_candidate_preserves_locked_hero(
    db_session: Session,
    test_settings: object,
    locked_hero_slide: tuple[Presentation, SlideSpec, HeroFingerprint],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Workflow _pick_safe_candidate must merge locked hero from current plan before save."""
    from archium.domain.visual.defaults import default_presentation_design_system
    from archium.domain.visual.validation import LayoutValidationReport
    from archium.workflow.visual_nodes import VisualWorkflowNodes, VisualWorkflowRuntime

    _presentation, slide, baseline = locked_hero_slide
    plans = LayoutPlanRepository(db_session)
    design = DesignSystemRepository(db_session).save(default_presentation_design_system())
    current = _load_slide_plan(db_session, slide)
    alternate = plans.save(
        current.model_copy(
            update={
                "id": uuid4(),
                "layout_variant": "workflow_fallback",
                "version": current.version + 1,
                "elements": [
                    element.model_copy(
                        update={
                            "x": 9.0,
                            "y": 9.0,
                            "width": 0.5,
                            "height": 0.5,
                            "content_ref": "assets/replaced.png",
                            "locked": False,
                        }
                    )
                    if element.id == "hero"
                    else element.model_copy(update={"x": element.x + 0.5})
                    for element in current.elements
                ],
            }
        )
    )

    def _validate(self, plan, design_system, **kwargs):  # noqa: ANN001, ARG001
        if plan.id == alternate.id:
            return LayoutValidationReport(issues=[], score=1.0)
        return LayoutValidationReport(issues=[], score=0.0, valid=False)

    monkeypatch.setattr(
        "archium.application.visual.layout_validation_service.LayoutValidationService.validate",
        _validate,
    )

    runtime = VisualWorkflowRuntime(db_session, settings=test_settings)  # type: ignore[arg-type]
    nodes = VisualWorkflowNodes(runtime)
    replacement = nodes._pick_safe_candidate(
        current_id=str(current.id),
        candidate_ids=[str(current.id), str(alternate.id)],
        design=design,
        state={},
    )
    assert replacement is not None
    assert replacement.id != current.id
    assert _hero_fingerprint(replacement) == baseline
