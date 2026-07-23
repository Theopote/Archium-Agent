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
from archium.domain.enums import ApprovalStatus
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
            status=ApprovalStatus.APPROVED.value,
        ),
    )
    db_session.commit()
    assert updated.status == ApprovalStatus.CHANGES_PENDING


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
    assert brief.status == ApprovalStatus.PENDING


def test_regenerate_missing_page_raises(db_session: Session) -> None:
    saved_outline = _seed_outline(db_session)
    service = SlideDesignBriefService(db_session)
    with pytest.raises(WorkflowError, match="SlideIntent"):
        service.regenerate_page(saved_outline.id, page_order=99)


def test_generate_all_assigns_grammar_archetype_for_problem_page(
    db_session: Session,
) -> None:
    project = ProjectRepository(db_session).create(Project(name="Grammar Brief"))
    presentation = PresentationRepository(db_session).create_presentation(
        Presentation(project_id=project.id, title="医院汇报")
    )
    outline = OutlinePlan(
        id=uuid4(),
        presentation_id=presentation.id,
        title="医院汇报",
        thesis="老院区更新需要回应现状问题并给出可实施策略。",
        audience="院领导",
        purpose="方案汇报",
        sections=[
            OutlineSection(
                id="s1",
                title="现状",
                purpose="诊断",
                key_message="问题清晰",
                order=0,
            )
        ],
        page_intents=[
            SlideIntent(
                order=0,
                page_task="老院区更新开篇：历史与目标",
                central_conclusion="历史院区面临矛盾，更新目标是可持续运营。",
                expected_layout="",
            ),
            SlideIntent(
                order=3,
                page_task="现状问题诊断",
                central_conclusion="急诊流线交叉导致拥堵。",
                required_evidence=["现场照片", "问题编号"],
                expected_layout="photo_evidence_grid",
            ),
        ],
    )
    saved = PresentationRepository(db_session).save_outline(outline)
    briefs = SlideDesignBriefService(db_session).generate_all(saved.id)
    refreshed = PresentationRepository(db_session).get_outline(saved.id)
    assert refreshed is not None

    opening = next(b for b in briefs if b.page_order == 0)
    diagnosis = next(b for b in briefs if b.page_order == 3)
    assert opening.page_archetype is not None
    assert opening.page_archetype.value == "narrative_opening"
    assert diagnosis.page_archetype is not None
    assert diagnosis.page_archetype.value == "site_problem_diagnosis"
    assert any("grammar:" in item for item in diagnosis.required_content)

    intent_diag = next(i for i in refreshed.page_intents if i.order == 3)
    assert intent_diag.page_archetype is not None
    assert intent_diag.page_archetype.value == "site_problem_diagnosis"


def test_update_brief_sets_page_archetype_and_syncs_intent(db_session: Session) -> None:
    saved_outline = _seed_outline(db_session)
    service = SlideDesignBriefService(db_session)
    service.generate_all(saved_outline.id)
    updated = service.update_brief(
        saved_outline.id,
        SlideDesignBriefUpdate(
            page_order=0,
            page_task="老院区更新开篇",
            central_claim="建立叙事张力",
            primary_visual_type="photo",
            page_archetype="narrative_opening",
            required_content=["历史语境"],
            status=ApprovalStatus.PENDING.value,
        ),
    )
    db_session.commit()
    assert updated.page_archetype is not None
    assert updated.page_archetype.value == "narrative_opening"
    assert any("historic_or_context_photo" in item for item in updated.required_content)

    outline = PresentationRepository(db_session).get_outline(saved_outline.id)
    assert outline is not None
    intent = next(item for item in outline.page_intents if item.order == 0)
    assert intent.page_archetype is not None
    assert intent.page_archetype.value == "narrative_opening"

