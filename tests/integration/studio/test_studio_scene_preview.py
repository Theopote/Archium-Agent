"""Studio load path prefers RenderScene preview."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from archium.config.settings import Settings
from archium.domain.enums import ApprovalStatus, SlideType
from archium.domain.presentation import Presentation, PresentationBrief, Storyline
from archium.domain.project import Project
from archium.domain.slide import SlideSpec
from archium.domain.visual.defaults import default_presentation_design_system
from archium.domain.visual.enums import LayoutContentType, LayoutElementRole, LayoutFamily
from archium.domain.visual.layout import LayoutElement, LayoutPlan
from archium.infrastructure.database.repositories import PresentationRepository, ProjectRepository
from archium.infrastructure.database.visual_repositories import (
    DesignSystemRepository,
    LayoutPlanRepository,
)
from archium.ui.studio_service import load_studio_context
from sqlalchemy.orm import Session


def test_load_studio_context_uses_scene_preview(
    db_session: Session,
    tmp_path: Path,
    monkeypatch,
) -> None:
    settings = Settings(_env_file=None, output_path=tmp_path)
    monkeypatch.setattr(
        "archium.ui.studio_service._resolve_runtime_settings",
        lambda _settings=None: settings,
    )

    project = ProjectRepository(db_session).create(Project(name="Studio Context Project"))
    presentations = PresentationRepository(db_session)
    presentation = presentations.create_presentation(
        Presentation(project_id=project.id, title="Context Deck")
    )
    brief = presentations.save_brief(
        PresentationBrief(
            project_id=project.id,
            presentation_id=presentation.id,
            title="Context Deck",
            audience="甲方",
            purpose="集成测试",
            core_message="Studio 应优先显示 RenderScene 预览。",
            approval_status=ApprovalStatus.APPROVED,
        )
    )
    storyline = presentations.save_storyline(
        Storyline(
            presentation_id=presentation.id,
            thesis="场景预览优先。",
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
            title="Page",
            slide_type=SlideType.CONTENT,
            order=0,
            chapter_id="ch1",
            message="本页用于验证 Studio 加载时编译 RenderScene。",
        )
    )
    plan = LayoutPlanRepository(db_session).save(
        LayoutPlan(
            slide_id=slide.id,
            layout_family=LayoutFamily.TEXTUAL_ARGUMENT,
            layout_variant="two_column",
            page_width=10,
            page_height=5.625,
            hero_element_id="title",
            reading_order=["title"],
            whitespace_ratio=0.35,
            elements=[
                LayoutElement(
                    id="title",
                    role=LayoutElementRole.TITLE,
                    content_type=LayoutContentType.TEXT,
                    text_content="策略标题",
                    x=0.8,
                    y=0.5,
                    width=8.0,
                    height=0.7,
                ),
            ],
            design_system_id=design.id,
            visual_intent_id=uuid4(),
        )
    )
    presentations.save_slide(slide.model_copy(update={"layout_plan_id": plan.id}))

    context = load_studio_context(db_session, project.id, presentation.id)
    assert context is not None
    assert context.preview_ready_count == 1
    snap = context.snapshot.slides[0]
    assert snap.preview_kind == "scene"
    assert snap.render_scene is not None
    assert snap.preview_image is not None
    assert Path(snap.preview_image).is_file()
    assert "studio-scene-previews" in snap.preview_image.replace("\\", "/")
