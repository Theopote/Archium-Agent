"""Unit tests for SceneProposalRepository persistence."""

from __future__ import annotations

from uuid import uuid4

from archium.domain.enums import ApprovalStatus, SlideType
from archium.domain.presentation import Presentation, PresentationBrief, Storyline
from archium.domain.project import Project
from archium.domain.slide import SlideSpec
from archium.domain.visual.defaults import default_presentation_design_system
from archium.domain.visual.enums import LayoutContentType, LayoutElementRole, LayoutFamily
from archium.domain.visual.layout import LayoutElement, LayoutPlan
from archium.domain.visual.render_scene import (
    BackgroundStyle,
    RenderScene,
    TextNode,
    compute_scene_hash,
)
from archium.domain.visual.scene_change_proposal import (
    ProposalStatus,
    SceneChangeProposal,
)
from archium.infrastructure.database.repositories import PresentationRepository, ProjectRepository
from archium.infrastructure.database.visual_repositories import (
    DesignSystemRepository,
    LayoutPlanRepository,
    RenderSceneRepository,
    SceneProposalRepository,
)
from sqlalchemy.orm import Session


def _seed_slide_with_scene(session: Session) -> tuple[Presentation, SlideSpec, RenderScene]:
    project = ProjectRepository(session).create(Project(name="Proposal Repo Project"))
    presentations = PresentationRepository(session)
    presentation = presentations.create_presentation(
        Presentation(project_id=project.id, title="Proposal Deck")
    )
    brief = presentations.save_brief(
        PresentationBrief(
            project_id=project.id,
            presentation_id=presentation.id,
            title="Proposal Deck",
            audience="甲方",
            purpose="测试",
            core_message="Scene proposal 持久化。",
            approval_status=ApprovalStatus.APPROVED,
        )
    )
    storyline = presentations.save_storyline(
        Storyline(
            presentation_id=presentation.id,
            thesis="提案仓储验收。",
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
            message="本页用于验证 SceneChangeProposal 持久化。",
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
                x=1.0,
                y=1.0,
                width=8.0,
                height=1.0,
                z_index=1,
            )
        ],
        design_system_id=design.id,
        visual_intent_id=uuid4(),
    )
    plan = LayoutPlanRepository(session).save(plan)
    presentations.save_slide(slide.model_copy(update={"layout_plan_id": plan.id}))
    slide = presentations.get_slide(slide.id)
    assert slide is not None

    scene = RenderScene(
        slide_id=slide.id,
        layout_plan_id=plan.id,
        page_width=10,
        page_height=5.625,
        background=BackgroundStyle(color="#FFFFFF"),
        nodes=[
            TextNode(
                id="title",
                x=1.0,
                y=1.0,
                width=8.0,
                height=1.0,
                z_index=1,
                text="旧标题",
                font_family="Arial",
                font_size=24,
                color="#000000",
                line_height=1.2,
            )
        ],
    )
    saved_scene = RenderSceneRepository(session).save(scene)
    return presentation, slide, saved_scene


def _build_proposal(
    *,
    presentation_id,
    slide_id,
    base_scene: RenderScene,
) -> SceneChangeProposal:
    proposed = base_scene.model_copy(deep=True)
    title = proposed.node_by_id("title")
    assert isinstance(title, TextNode)
    title.text = "新标题"
    return SceneChangeProposal(
        presentation_id=presentation_id,
        slide_id=slide_id,
        base_scene_hash=compute_scene_hash(base_scene),
        base_scene=base_scene,
        proposed_scene=proposed,
        patch_actions=[],
        status=ProposalStatus.READY,
    )


def test_scene_proposal_repository_round_trip(db_session: Session) -> None:
    presentation, slide, base_scene = _seed_slide_with_scene(db_session)
    proposal = _build_proposal(
        presentation_id=presentation.id,
        slide_id=slide.id,
        base_scene=base_scene,
    )

    repo = SceneProposalRepository(db_session)
    saved = repo.save(proposal)

    assert saved.proposal_id == proposal.proposal_id
    assert saved.base_scene_id is not None
    assert saved.base_scene_id != base_scene.id
    assert saved.proposed_scene_id is not None
    assert saved.proposed_scene_id != base_scene.id
    assert saved.proposed_scene_id != saved.base_scene_id
    assert saved.base_scene_hash == compute_scene_hash(base_scene)
    assert saved.proposed_scene.node_by_id("title").text == "新标题"  # type: ignore[union-attr]
    assert saved.status == ProposalStatus.READY
    # Live canonical scene must remain untouched after proposal snapshotting.
    live = RenderSceneRepository(db_session).get(base_scene.id)
    assert live is not None
    assert live.node_by_id("title").text == "旧标题"  # type: ignore[union-attr]

    loaded = repo.get(saved.proposal_id)
    assert loaded is not None
    assert loaded.proposal_id == saved.proposal_id
    assert loaded.proposed_scene.node_by_id("title").text == "新标题"  # type: ignore[union-attr]
    assert loaded.qa_before == saved.qa_before
    assert loaded.qa_after == saved.qa_after


def test_scene_proposal_repository_active_for_slide(db_session: Session) -> None:
    presentation, slide, base_scene = _seed_slide_with_scene(db_session)
    repo = SceneProposalRepository(db_session)

    first = repo.save(
        _build_proposal(
            presentation_id=presentation.id,
            slide_id=slide.id,
            base_scene=base_scene,
        )
    )
    second = repo.save(
        _build_proposal(
            presentation_id=presentation.id,
            slide_id=slide.id,
            base_scene=base_scene,
        )
    )

    reloaded_first = repo.get(first.proposal_id)
    assert reloaded_first is not None
    assert reloaded_first.status == ProposalStatus.SUPERSEDED

    active = repo.get_active_for_slide(slide.id)
    assert active is not None
    assert active.proposal_id == second.proposal_id
    assert active.status == ProposalStatus.READY


def test_scene_proposal_repository_persists_decision(db_session: Session) -> None:
    from archium.application.visual.scene_proposal_service import SceneProposalService
    from archium.config.settings import Settings

    presentation, slide, base_scene = _seed_slide_with_scene(db_session)
    repo = SceneProposalRepository(db_session)
    proposal = repo.save(
        _build_proposal(
            presentation_id=presentation.id,
            slide_id=slide.id,
            base_scene=base_scene,
        )
    )

    service = SceneProposalService(db_session, settings=Settings())
    rejected = service.reject_proposal(proposal, notes="Not now")

    loaded = repo.get(proposal.proposal_id)
    assert loaded is not None
    assert loaded.status == ProposalStatus.REJECTED
    assert loaded.decision is not None
    assert loaded.decision.notes == "Not now"
    assert loaded.decision.rejected_action_ids == []
    assert loaded.decided_at is not None
    assert rejected.status == ProposalStatus.REJECTED
    assert repo.get_active_for_slide(slide.id) is None


def test_scene_proposal_repository_superseded_status(db_session: Session) -> None:
    presentation, slide, base_scene = _seed_slide_with_scene(db_session)
    repo = SceneProposalRepository(db_session)
    proposal = repo.save(
        _build_proposal(
            presentation_id=presentation.id,
            slide_id=slide.id,
            base_scene=base_scene,
        )
    )

    superseded = proposal.model_copy(
        update={
            "status": ProposalStatus.SUPERSEDED,
        }
    )
    from archium.application.visual.scene_proposal_service import SceneProposalService
    from archium.config.settings import Settings

    service = SceneProposalService(db_session, settings=Settings())
    updated = service.mark_proposal_superseded(superseded)

    loaded = repo.get(proposal.proposal_id)
    assert loaded is not None
    assert loaded.status == ProposalStatus.SUPERSEDED
    assert loaded.decided_at is not None
    assert updated.status == ProposalStatus.SUPERSEDED


def test_accept_proposal_keeps_live_scene_as_proposed(db_session: Session) -> None:
    """Accept must not be undone by the subsequent proposal metadata save."""
    from archium.application.visual.scene_proposal_service import SceneProposalService
    from archium.config.settings import Settings
    from archium.domain.visual.studio_command import RewriteTextCommand

    presentation, slide, base_scene = _seed_slide_with_scene(db_session)
    service = SceneProposalService(db_session, settings=Settings())
    proposal = service.create_proposal(
        base_scene=base_scene,
        commands=[
            RewriteTextCommand(
                presentation_id=presentation.id,
                slide_id=slide.id,
                node_id="title",
                new_text="新标题",
            )
        ],
        presentation_id=presentation.id,
        slide_id=slide.id,
    )
    proposal = service.save_proposal(proposal)

    result = service.accept_proposal(proposal, slide, current_scene=base_scene)
    live = RenderSceneRepository(db_session).get(base_scene.id)
    assert live is not None
    title = live.node_by_id("title")
    assert isinstance(title, TextNode)
    assert title.text == "新标题"
    assert result.proposal.status == ProposalStatus.ACCEPTED

    plan = LayoutPlanRepository(db_session).get(slide.layout_plan_id)  # type: ignore[arg-type]
    assert plan is not None
    title_el = next(el for el in plan.elements if el.id == "title")
    assert title_el.text_content == "新标题"

