"""Tests for SlideDesignBriefService."""

from __future__ import annotations

from uuid import uuid4

import pytest
from archium.application.review_models import SlideDesignBriefUpdate
from archium.application.slide_design_brief_service import (
    SlideDesignBriefService,
    design_briefs_ready,
)
from archium.domain.outline import OutlinePlan, OutlineSection
from archium.domain.presentation import Presentation
from archium.domain.project import Project
from archium.domain.slide_design_brief import BriefStatus
from archium.domain.slide_intent import SlideIntent
from archium.exceptions import WorkflowError
from archium.infrastructure.database.repositories import (
    PresentationRepository,
    ProjectRepository,
)
from sqlalchemy.orm import Session


def _seed_outline(session: Session) -> OutlinePlan:
    project = ProjectRepository(session).create(Project(name="Brief Test"))
    presentation = PresentationRepository(session).create_presentation(
        Presentation(project_id=project.id, title="测试汇报")
    )
    outline = OutlinePlan(
        id=uuid4(),
        presentation_id=presentation.id,
        title="测试汇报",
        thesis="中心论点需要足够长度以满足校验要求。",
        audience="院领导",
        purpose="方案汇报",
        sections=[
            OutlineSection(
                id="s1",
                title="策略",
                purpose="解释策略",
                key_message="结论一",
                order=0,
            )
        ],
        page_intents=[
            SlideIntent(
                order=0,
                page_task="解释交通组织",
                central_conclusion="环形交通分离流线",
                expected_layout="drawing_focus",
                forbidden_content=["参考案例替代项目图纸"],
            ),
            SlideIntent(
                order=1,
                page_task="现场照片",
                expected_layout="photo_evidence_grid",
            ),
        ],
    )
    return PresentationRepository(session).save_outline(outline)


def test_generate_all_creates_drawing_protection_rules(db_session: Session) -> None:
    saved_outline = _seed_outline(db_session)
    service = SlideDesignBriefService(db_session)
    briefs = service.generate_all(saved_outline.id)
    db_session.commit()

    assert len(briefs) == 2
    drawing_brief = next(b for b in briefs if b.page_order == 0)
    assert drawing_brief.primary_visual_type == "drawing"
    assert drawing_brief.drawing_policy is not None
    assert drawing_brief.drawing_policy.forbid_cover_crop is True
    assert any("禁止 cover 裁剪" in rule for rule in drawing_brief.protection_rules)


def test_edit_approved_brief_becomes_changes_pending(db_session: Session) -> None:
    saved_outline = _seed_outline(db_session)
    service = SlideDesignBriefService(db_session)
    service.generate_all(saved_outline.id)
    service.approve_all(saved_outline.id)
    updated = service.update_brief(
        saved_outline.id,
        SlideDesignBriefUpdate(
            page_order=0,
            page_task="修改后的任务",
            central_claim="新结论",
            primary_visual_type="photo",
            status=BriefStatus.APPROVED.value,
        ),
    )
    db_session.commit()
    assert updated.status == BriefStatus.CHANGES_PENDING


def test_design_briefs_ready_requires_all_approved(db_session: Session) -> None:
    saved_outline = _seed_outline(db_session)
    service = SlideDesignBriefService(db_session)
    service.generate_all(saved_outline.id)
    db_session.commit()

    outline = PresentationRepository(db_session).get_outline(saved_outline.id)
    assert outline is not None
    ready, missing = design_briefs_ready(outline)
    assert ready is False
    assert missing

    service.approve_all(saved_outline.id)
    db_session.commit()
    outline = PresentationRepository(db_session).get_outline(saved_outline.id)
    assert outline is not None
    ready, missing = design_briefs_ready(outline)
    assert ready is True
    assert not missing


def test_regenerate_single_page(db_session: Session) -> None:
    saved_outline = _seed_outline(db_session)
    service = SlideDesignBriefService(db_session)
    service.generate_all(saved_outline.id)
    brief = service.regenerate_page(saved_outline.id, page_order=1)
    db_session.commit()
    assert brief.page_order == 1
    assert brief.status == BriefStatus.READY_FOR_REVIEW


def test_regenerate_missing_page_raises(db_session: Session) -> None:
    saved_outline = _seed_outline(db_session)
    service = SlideDesignBriefService(db_session)
    with pytest.raises(WorkflowError, match="SlideIntent"):
        service.regenerate_page(saved_outline.id, page_order=99)
