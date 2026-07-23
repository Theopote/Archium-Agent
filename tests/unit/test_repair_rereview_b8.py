"""B8: repair → clear prior issues → four-layer re-review with round limits."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from archium.application.slide_repair_service import has_repairable_open_issues
from archium.config.settings import Settings
from archium.domain.enums import (
    ReviewCategory,
    ReviewLayer,
    ReviewSeverity,
    ReviewStatus,
)
from archium.domain.presentation import Presentation
from archium.domain.project import Project
from archium.domain.review import ReviewIssue
from archium.domain.review_rules import ReviewRuleCode
from archium.infrastructure.database.repositories import (
    PresentationRepository,
    ProjectRepository,
    ReviewRepository,
)
from archium.workflow.presentation_graph import PresentationWorkflowGraph
from sqlalchemy.orm import Session


def _issue(**overrides: object) -> ReviewIssue:
    base = {
        "presentation_id": uuid4(),
        "slide_id": uuid4(),
        "reviewer_layer": ReviewLayer.LAYOUT,
        "category": ReviewCategory.LENGTH,
        "severity": ReviewSeverity.MEDIUM,
        "rule_code": ReviewRuleCode.LAYOUT_HIGH_TEXT_DENSITY,
        "title": "页面信息密度过高",
        "description": "文本量过高",
        "auto_fixable": True,
        "status": ReviewStatus.OPEN,
    }
    base.update(overrides)
    return ReviewIssue(**base)  # type: ignore[arg-type]


def test_auto_fixable_issues_route_to_repair_even_when_llm_repair_disabled() -> None:
    settings = Settings(_env_file=None, slide_repair_enabled=False)
    assert has_repairable_open_issues([_issue()], settings) is True


def test_llm_repairable_issues_require_slide_repair_enabled() -> None:
    settings_off = Settings(_env_file=None, slide_repair_enabled=False)
    settings_on = Settings(_env_file=None, slide_repair_enabled=True)
    issue = _issue(
        auto_fixable=False,
        category=ReviewCategory.CONTENT,
        severity=ReviewSeverity.CRITICAL,
        rule_code=ReviewRuleCode.CONTENT_MISSING_MESSAGE,
        title="缺少核心信息",
        description="缺结论",
    )
    assert has_repairable_open_issues([issue], settings_off) is False
    assert has_repairable_open_issues([issue], settings_on) is True


def test_route_after_layout_review_respects_max_rounds() -> None:
    runtime = SimpleNamespace(
        settings=Settings(
            _env_file=None,
            slide_repair_enabled=False,
            slide_repair_max_rounds=1,
        )
    )
    graph = PresentationWorkflowGraph.__new__(PresentationWorkflowGraph)
    graph._runtime = runtime  # type: ignore[attr-defined]
    issue = _issue()

    assert (
        graph._route_after_layout_review(  # type: ignore[attr-defined]
            {"errors": [], "repair_round": 0, "review_issues": [issue]}
        )
        == "repair"
    )
    assert (
        graph._route_after_layout_review(  # type: ignore[attr-defined]
            {"errors": [], "repair_round": 1, "review_issues": [issue]}
        )
        == "validate"
    )


def test_resolve_open_for_presentation_clears_prior_keeps_excluded(
    db_session: Session,
) -> None:
    project = ProjectRepository(db_session).create(Project(name="B8 clear"))
    presentation = PresentationRepository(db_session).create_presentation(
        Presentation(project_id=project.id, title="B8")
    )
    repo = ReviewRepository(db_session)
    prior = repo.create(
        ReviewIssue(
            presentation_id=presentation.id,
            slide_id=uuid4(),
            category=ReviewCategory.CONTENT,
            severity=ReviewSeverity.HIGH,
            rule_code=ReviewRuleCode.CONTENT_MISSING_MESSAGE,
            title="旧问题",
            description="应被清空",
        )
    )
    pending = repo.create(
        ReviewIssue(
            presentation_id=presentation.id,
            slide_id=uuid4(),
            category=ReviewCategory.LENGTH,
            severity=ReviewSeverity.MEDIUM,
            rule_code=ReviewRuleCode.LAYOUT_HIGH_TEXT_DENSITY,
            title="需人工确认版面调整",
            description="保留",
            auto_fixable=False,
        )
    )

    cleared = repo.resolve_open_for_presentation(
        presentation.id,
        exclude_ids={pending.id},
    )
    assert cleared == 1
    assert repo.get_by_id(prior.id).status == ReviewStatus.RESOLVED  # type: ignore[union-attr]
    assert repo.get_by_id(pending.id).status == ReviewStatus.OPEN  # type: ignore[union-attr]


def test_repair_clears_sibling_open_issues_for_rereview(db_session: Session) -> None:
    """Successful rule repair resolves the fixed issue and other prior OPEN siblings."""
    from archium.application.slide_repair_service import SlideRepairService
    from archium.domain.enums import SlideStatus, SlideType
    from archium.domain.slide import SlideSpec

    project = ProjectRepository(db_session).create(Project(name="B8 sibling"))
    presentation = PresentationRepository(db_session).create_presentation(
        Presentation(project_id=project.id, title="B8 sibling")
    )
    slide = PresentationRepository(db_session).save_slide(
        SlideSpec(
            presentation_id=presentation.id,
            chapter_id="ch1",
            order=0,
            title="综合结论",
            message="这是一段较长的核心结论用于测试版面密度" * 12,
            slide_type=SlideType.CONTENT,
            key_points=[f"要点描述内容 {index}" * 4 for index in range(5)],
            status=SlideStatus.PLANNED,
        )
    )
    repo = ReviewRepository(db_session)
    density = repo.create(
        ReviewIssue(
            presentation_id=presentation.id,
            slide_id=slide.id,
            category=ReviewCategory.LENGTH,
            severity=ReviewSeverity.MEDIUM,
            rule_code=ReviewRuleCode.LAYOUT_HIGH_TEXT_DENSITY,
            title="页面信息密度过高",
            description="文本量过高",
            auto_fixable=True,
        )
    )
    sibling = repo.create(
        ReviewIssue(
            presentation_id=presentation.id,
            slide_id=slide.id,
            category=ReviewCategory.CONTENT,
            severity=ReviewSeverity.HIGH,
            rule_code=ReviewRuleCode.CONTENT_MISSING_MESSAGE,
            title="旧层问题",
            description="四层复审前应清空",
        )
    )

    SlideRepairService(
        db_session,
        llm=None,
        settings=Settings(_env_file=None, slide_repair_enabled=False),
    ).repair_slides(presentation.id, [slide], [density, sibling])

    assert repo.get_by_id(density.id).status == ReviewStatus.RESOLVED  # type: ignore[union-attr]
    assert repo.get_by_id(sibling.id).status == ReviewStatus.RESOLVED  # type: ignore[union-attr]
