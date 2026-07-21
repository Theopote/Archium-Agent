"""Unit tests for Studio RenderScene compile / preview service."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from archium.application.visual.render_scene_compiler import RenderSceneCompiler
from archium.application.visual.scene_repair_service import SceneRepairService
from archium.application.visual.studio_scene_service import StudioSceneService
from archium.config.settings import Settings
from archium.domain.enums import ApprovalStatus, SlideType
from archium.domain.presentation import Presentation, PresentationBrief, Storyline
from archium.domain.project import Project
from archium.domain.slide import SlideSpec
from archium.domain.visual.defaults import default_presentation_design_system
from archium.domain.visual.enums import LayoutContentType, LayoutElementRole, LayoutFamily
from archium.domain.visual.layout import LayoutElement, LayoutPlan
from archium.domain.visual.render_scene import compute_scene_hash
from archium.infrastructure.database.repositories import PresentationRepository, ProjectRepository
from archium.infrastructure.database.visual_repositories import (
    DesignSystemRepository,
    LayoutPlanRepository,
    RenderSceneRepository,
)
from archium.infrastructure.renderers.canvas_renderer import CanvasRenderer
from sqlalchemy.orm import Session


def _seed_slide_with_plan(session: Session) -> tuple[Presentation, SlideSpec, LayoutPlan]:
    project = ProjectRepository(session).create(Project(name="Studio Scene Project"))
    presentations = PresentationRepository(session)
    presentation = presentations.create_presentation(
        Presentation(project_id=project.id, title="Scene Deck")
    )
    brief = presentations.save_brief(
        PresentationBrief(
            project_id=project.id,
            presentation_id=presentation.id,
            title="Scene Deck",
            audience="甲方",
            purpose="测试",
            core_message="RenderScene 编译持久化。",
            approval_status=ApprovalStatus.APPROVED,
        )
    )
    storyline = presentations.save_storyline(
        Storyline(
            presentation_id=presentation.id,
            thesis="场景服务验收。",
            approval_status=ApprovalStatus.APPROVED,
        )
    )
    presentation.current_brief_id = brief.id
    presentation.current_storyline_id = storyline.id
    presentations.update_presentation(presentation)

    design = DesignSystemRepository(session).save(default_presentation_design_system())
    slide = presentations.save_slide(
        SlideSpec(
            presentation_id=presentation.id,
            title="Hero",
            slide_type=SlideType.CONTENT,
            order=0,
            chapter_id="ch1",
            message="本页用于验证 Studio RenderScene 编译与预览缓存。",
        )
    )
    plan = LayoutPlan(
        slide_id=slide.id,
        layout_family=LayoutFamily.HERO,
        layout_variant="centered",
        page_width=10,
        page_height=5.625,
        hero_element_id="title",
        reading_order=["title"],
        whitespace_ratio=0.4,
        elements=[
            LayoutElement(
                id="title",
                role=LayoutElementRole.TITLE,
                content_type=LayoutContentType.TEXT,
                text_content="院区总平面",
                x=0.8,
                y=0.5,
                width=8.4,
                height=0.8,
            ),
        ],
        design_system_id=design.id,
        visual_intent_id=uuid4(),
    )
    plan = LayoutPlanRepository(session).save(plan)
    presentations.save_slide(slide.model_copy(update={"layout_plan_id": plan.id}))
    slide = presentations.get_slide(slide.id)
    assert slide is not None
    return presentation, slide, plan


def test_canvas_renderer_exposes_node_bounds() -> None:
    slide_id = uuid4()
    plan = LayoutPlan(
        slide_id=slide_id,
        layout_family=LayoutFamily.HERO,
        layout_variant="centered",
        page_width=10,
        page_height=5.625,
        hero_element_id="title",
        reading_order=["title"],
        whitespace_ratio=0.4,
        elements=[
            LayoutElement(
                id="title",
                role=LayoutElementRole.TITLE,
                content_type=LayoutContentType.TEXT,
                text_content="标题",
                x=1.0,
                y=1.0,
                width=4.0,
                height=0.6,
            ),
        ],
        design_system_id=uuid4(),
        visual_intent_id=uuid4(),
    )
    scene = RenderSceneCompiler().compile(
        slide=SlideSpec(
            id=slide_id,
            presentation_id=uuid4(),
            title="T",
            slide_type=SlideType.CONTENT,
            order=0,
            chapter_id="ch1",
            message="画布节点边界单元测试。",
        ),
        layout_plan=plan,
        design_system=default_presentation_design_system(),
    )
    bounds = CanvasRenderer().node_bounds(scene)
    assert bounds
    assert any(item.source_layout_element_id == "title" for item in bounds)


def test_studio_scene_service_compiles_persists_and_previews(
    db_session: Session,
    tmp_path: Path,
) -> None:
    _presentation, slide, plan = _seed_slide_with_plan(db_session)
    settings = Settings(_env_file=None, output_path=tmp_path)
    service = StudioSceneService(db_session, settings=settings)

    first = service.ensure_scene_for_slide(slide.id)
    assert first is not None
    assert first.preview_path.is_file()
    assert first.reused is False
    assert RenderSceneRepository(db_session).get_by_layout_plan(plan.id) is not None

    second = service.ensure_scene_for_slide(slide.id)
    assert second is not None
    assert second.reused is True
    assert second.scene.id == first.scene.id
    assert compute_scene_hash(second.scene) == first.scene_hash


def test_studio_scene_refresh_after_layout_edit(db_session: Session, tmp_path: Path) -> None:
    presentation, slide, plan = _seed_slide_with_plan(db_session)
    settings = Settings(_env_file=None, output_path=tmp_path)
    service = StudioSceneService(db_session, settings=settings)
    first = service.ensure_scene_for_slide(slide.id)
    assert first is not None

    plans = LayoutPlanRepository(db_session)
    title = plan.element_by_id("title")
    assert title is not None
    updated = plan.model_copy(
        update={
            "elements": [
                title.model_copy(update={"text_content": "更新后的标题", "x": 1.5}),
                *[el for el in plan.elements if el.id != "title"],
            ]
        }
    )
    updated = plans.save(updated)
    refreshed = service.refresh_after_layout_edit(
        presentation_id=presentation.id,
        plan=updated,
        slide_id=slide.id,
    )
    assert refreshed is not None
    assert refreshed.reused is False
    assert refreshed.scene_hash != first.scene_hash
    assert refreshed.preview_path.is_file()


def test_ensure_scene_runs_repair_before_preview(
    db_session: Session,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _presentation, slide, _plan = _seed_slide_with_plan(db_session)
    settings = Settings(_env_file=None, output_path=tmp_path, scene_repair_enabled=True)
    service = StudioSceneService(db_session, settings=settings)
    calls: list[int] = []
    original = SceneRepairService.repair_deck

    def _tracking(self, presentation_id, scenes, **kwargs):
        calls.append(len(scenes))
        return original(self, presentation_id, scenes, **kwargs)

    monkeypatch.setattr(SceneRepairService, "repair_deck", _tracking)
    result = service.ensure_scene_for_slide(slide.id)
    assert result is not None
    assert calls == [1]

    calls.clear()
    second = service.ensure_scene_for_slide(slide.id)
    assert second is not None
    assert second.reused is True
    assert calls == [1]


def test_ensure_scene_skips_repair_when_disabled(
    db_session: Session,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _presentation, slide, _plan = _seed_slide_with_plan(db_session)
    settings = Settings(
        _env_file=None,
        output_path=tmp_path,
        scene_repair_enabled=False,
    )
    service = StudioSceneService(db_session, settings=settings)
    calls: list[int] = []

    def _tracking(self, presentation_id, scenes, **kwargs):
        calls.append(1)
        return SceneRepairService.repair_deck(self, presentation_id, scenes, **kwargs)

    monkeypatch.setattr(SceneRepairService, "repair_deck", _tracking)
    result = service.ensure_scene_for_slide(slide.id)
    assert result is not None
    assert calls == []
