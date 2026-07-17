"""Tests for PresentationRepository."""

from __future__ import annotations

from uuid import UUID

import pytest
from archium.domain.enums import (
    PresentationType,
    ProjectType,
    ReviewCategory,
    ReviewSeverity,
    SlideType,
    VisualType,
)
from archium.domain.presentation import Chapter, Presentation, PresentationBrief, Storyline
from archium.domain.project import Project
from archium.domain.review import ReviewIssue
from archium.domain.slide import SlideSpec, VisualRequirement
from archium.infrastructure.database.repositories import (
    PresentationRepository,
    ProjectRepository,
    ReviewRepository,
)
from sqlalchemy.orm import Session


@pytest.fixture
def project_id(db_session: Session) -> UUID:
    return ProjectRepository(db_session).create(
        Project(name="某医院老院区更新", project_type=ProjectType.HEALTHCARE)
    ).id


@pytest.fixture
def pres_repo(db_session: Session) -> PresentationRepository:
    return PresentationRepository(db_session)


def test_create_presentation(pres_repo: PresentationRepository, project_id: UUID) -> None:
    pres = pres_repo.create_presentation(
        Presentation(project_id=project_id, title="老院区更新概念汇报")
    )
    fetched = pres_repo.get_presentation(pres.id)
    assert fetched is not None
    assert fetched.title == "老院区更新概念汇报"


def test_save_and_get_brief(pres_repo: PresentationRepository, project_id: UUID) -> None:
    pres = pres_repo.create_presentation(
        Presentation(project_id=project_id, title="概念汇报")
    )
    brief = PresentationBrief(
        project_id=project_id,
        presentation_id=pres.id,
        title="概念汇报 Brief",
        presentation_type=PresentationType.CLIENT_REVIEW,
        audience="医院管理层",
        purpose="确认总体改造方向",
        duration_minutes=20,
        target_slide_count=20,
        core_message="以交通重组、立面更新和公共空间提升改善老院区整体体验",
        required_sections=["现状分析", "改造策略"],
    )
    saved = pres_repo.save_brief(brief)
    fetched = pres_repo.get_brief(saved.id)
    assert fetched is not None
    assert fetched.audience == "医院管理层"
    assert fetched.version == 1


def test_list_briefs_by_version(pres_repo: PresentationRepository, project_id: UUID) -> None:
    pres = pres_repo.create_presentation(
        Presentation(project_id=project_id, title="汇报")
    )
    brief_v1 = pres_repo.save_brief(
        PresentationBrief(
            project_id=project_id,
            presentation_id=pres.id,
            title="Brief v1",
            audience="甲方",
            purpose="决策",
            core_message="核心信息",
            version=1,
        )
    )
    brief_v2 = pres_repo.save_brief(
        PresentationBrief(
            project_id=project_id,
            presentation_id=pres.id,
            title="Brief v2",
            audience="甲方",
            purpose="决策",
            core_message="更新后的核心信息",
            version=2,
        )
    )
    briefs = pres_repo.list_briefs(pres.id)
    assert len(briefs) == 2
    assert briefs[0].id == brief_v2.id
    assert briefs[1].id == brief_v1.id


def test_save_and_get_storyline(pres_repo: PresentationRepository, project_id: UUID) -> None:
    pres = pres_repo.create_presentation(
        Presentation(project_id=project_id, title="汇报")
    )
    storyline = Storyline(
        presentation_id=pres.id,
        thesis="通过交通重组改善老院区体验",
        chapters=[
            Chapter(
                id="ch1",
                title="现状与问题",
                purpose="建立改造必要性",
                key_message="交通是核心痛点",
                order=0,
            ),
            Chapter(
                id="ch2",
                title="改造策略",
                purpose="提出方向",
                key_message="交通重组带动品质提升",
                order=1,
            ),
        ],
    )
    saved = pres_repo.save_storyline(storyline)
    fetched = pres_repo.get_storyline(saved.id)
    assert fetched is not None
    assert len(fetched.chapters) == 2
    assert fetched.chapters[0].title == "现状与问题"


def test_save_and_list_slides(pres_repo: PresentationRepository, project_id: UUID) -> None:
    pres = pres_repo.create_presentation(
        Presentation(project_id=project_id, title="汇报")
    )
    slide = SlideSpec(
        presentation_id=pres.id,
        chapter_id="ch1",
        order=0,
        title="院区现状",
        message="现有交通组织无法满足医院日常运营需求",
        slide_type=SlideType.CONTENT,
        visual_requirements=[
            VisualRequirement(
                type=VisualType.SITE_PLAN,
                description="总平面图标注交通流线",
            )
        ],
    )
    pres_repo.save_slide(slide)
    slides = pres_repo.list_slides(pres.id)
    assert len(slides) == 1
    assert slides[0].message == slide.message


def test_review_repository(db_session: Session, pres_repo: PresentationRepository, project_id: UUID) -> None:
    pres = pres_repo.create_presentation(
        Presentation(project_id=project_id, title="汇报")
    )
    review_repo = ReviewRepository(db_session)
    issue = review_repo.create(
        ReviewIssue(
            presentation_id=pres.id,
            category=ReviewCategory.CITATION,
            severity=ReviewSeverity.HIGH,
            title="缺少来源引用",
            description="用地面积数据未关联文档来源",
        )
    )
    issues = review_repo.list_by_presentation(pres.id)
    assert len(issues) == 1
    assert issues[0].id == issue.id

    issue.resolve()
    updated = review_repo.update(issue)
    assert updated.status.value == "resolved"
