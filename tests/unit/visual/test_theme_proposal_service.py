"""ThemeChangeProposal service persistence and accept/reject behavior."""

from __future__ import annotations

import pytest
from archium.application.visual.theme_proposal_service import ThemeProposalService
from archium.domain.enums import ApprovalStatus, SlideType
from archium.domain.presentation import Presentation
from archium.domain.project import Project
from archium.domain.slide import SlideSpec
from archium.domain.visual.art_direction import ArtDirection
from archium.domain.visual.deck_theme_tokens import DeckThemeTokens
from archium.domain.visual.defaults import default_presentation_design_system
from archium.domain.visual.enums import ImageFit
from archium.domain.visual.page_quality import IssueSeverity, QualityIssue
from archium.domain.visual.theme_change_proposal import ThemeProposalStatus
from archium.exceptions import WorkflowError
from archium.infrastructure.database.repositories import PresentationRepository, ProjectRepository
from archium.infrastructure.database.visual_repositories import (
    ArtDirectionRepository,
    DesignSystemRepository,
)
from sqlalchemy.orm import Session


def _seed_theme_context(session: Session) -> tuple[Presentation, ArtDirection]:
    project = ProjectRepository(session).create(Project(name="Theme Tokens Project"))
    presentations = PresentationRepository(session)
    presentation = presentations.create_presentation(
        Presentation(project_id=project.id, title="Theme Deck")
    )
    presentations.save_slide(
        SlideSpec(
            presentation_id=presentation.id,
            title="Cover",
            slide_type=SlideType.CONTENT,
            order=0,
            chapter_id="ch1",
            message="风格提案测试页。",
        )
    )
    design = DesignSystemRepository(session).save(default_presentation_design_system())
    art = ArtDirectionRepository(session).save(
        ArtDirection(
            project_id=project.id,
            presentation_id=presentation.id,
            concept_name="冷静理性",
            rationale="用于 ThemeChangeProposal 验收。",
            palette_strategy="中性主色 + 强调色",
            typography_strategy="标题衬线 / 正文无衬线",
            grid_strategy="12 栏",
            image_strategy="照片可统一处理",
            drawing_strategy="图纸 contain",
            diagram_strategy="线稿清晰",
            annotation_strategy="细线标注",
            cover_strategy="大标题",
            section_strategy="章节页简洁",
            content_strategy="一页一结论",
            closing_strategy="行动号召",
            pacing_strategy="证据与策略交替",
            design_system_id=design.id,
            approval_status=ApprovalStatus.APPROVED,
        )
    )
    return presentation, art


def test_create_theme_proposal_persists_without_switching_art(
    db_session: Session,
) -> None:
    presentation, art = _seed_theme_context(db_session)
    original_ds_id = art.design_system_id
    service = ThemeProposalService(db_session)
    proposal = service.create_proposal(
        presentation.id,
        DeckThemeTokens(primary="#112233", accent="#AABBCC"),
    )
    assert proposal.status in {
        ThemeProposalStatus.READY,
        ThemeProposalStatus.READY_WITH_WARNINGS,
    }
    loaded = service.get(proposal.proposal_id)
    assert loaded is not None
    assert loaded.token_patch.primary == "#112233"
    assert loaded.proposed_design_system.colors.primary == "#112233"
    assert loaded.base_design_system.id == original_ds_id

    refreshed_art = ArtDirectionRepository(db_session).get(art.id)
    assert refreshed_art is not None
    assert refreshed_art.design_system_id == original_ds_id


def test_accept_switches_art_direction_design_system(db_session: Session) -> None:
    presentation, art = _seed_theme_context(db_session)
    service = ThemeProposalService(db_session)
    proposal = service.create_proposal(
        presentation.id,
        DeckThemeTokens(primary="#010101", title_font="SimSun"),
    )
    accepted = service.accept_proposal(proposal)
    assert accepted.status == ThemeProposalStatus.ACCEPTED
    refreshed_art = ArtDirectionRepository(db_session).get(art.id)
    assert refreshed_art is not None
    assert refreshed_art.design_system_id == accepted.proposed_design_system_id
    assert refreshed_art.design_system_id != proposal.base_design_system_id
    design = DesignSystemRepository(db_session).get(refreshed_art.design_system_id)
    assert design is not None
    assert design.colors.primary == "#010101"
    assert design.typography.title.font_family == "SimSun"
    assert "(theme proposal)" not in design.name


def test_reject_does_not_switch_design_system(db_session: Session) -> None:
    presentation, art = _seed_theme_context(db_session)
    original_ds_id = art.design_system_id
    service = ThemeProposalService(db_session)
    proposal = service.create_proposal(
        presentation.id,
        DeckThemeTokens(background="#F5F5F5"),
    )
    rejected = service.reject_proposal(proposal, notes="keep current")
    assert rejected.status == ThemeProposalStatus.REJECTED
    refreshed_art = ArtDirectionRepository(db_session).get(art.id)
    assert refreshed_art is not None
    assert refreshed_art.design_system_id == original_ds_id


def test_theme_tokens_never_force_drawing_cover(db_session: Session) -> None:
    presentation, _art = _seed_theme_context(db_session)
    service = ThemeProposalService(db_session)
    proposal = service.create_proposal(
        presentation.id,
        DeckThemeTokens(photo_treatment=None, corner_radius=0.08),
    )
    assert proposal.proposed_design_system.image_style.default_fit == ImageFit.CONTAIN


def test_accept_blockers_requires_allow_flag(db_session: Session) -> None:
    presentation, _art = _seed_theme_context(db_session)
    service = ThemeProposalService(db_session)
    proposal = service.create_proposal(
        presentation.id,
        DeckThemeTokens(primary="#ABCDEF"),
    )
    blocked = proposal.model_copy(
        update={
            "qa_summary": [
                QualityIssue(
                    code="THEME.TEST_BLOCKER",
                    message="synthetic blocker",
                    severity=IssueSeverity.BLOCKER,
                )
            ]
        }
    )
    with pytest.raises(WorkflowError, match="Blocker"):
        service.accept_proposal(blocked)
    forced = service.accept_proposal(blocked, allow_blockers=True)
    assert forced.status == ThemeProposalStatus.ACCEPTED
