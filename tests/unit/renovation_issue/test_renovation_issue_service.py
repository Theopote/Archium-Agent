"""Unit tests for renovation issue map planning."""

from __future__ import annotations

from uuid import uuid4

from archium.application.renovation_issue_service import (
    is_renovation_scenario,
    issue_map_fallback_from_brief,
    issue_map_from_draft,
    validate_issue_map,
)
from archium.domain.presentation import PresentationBrief
from archium.infrastructure.llm.presentation_schemas import (
    RenovationIssueDraft,
    RenovationIssueMapDraft,
    RenovationStrategyDraft,
)


def _renovation_brief() -> PresentationBrief:
    return PresentationBrief(
        project_id=uuid4(),
        presentation_id=uuid4(),
        title="老院区改造汇报",
        audience="医院管理层",
        purpose="老旧建筑改造提升",
        core_message="交通重组带动品质提升",
        required_sections=["现状分析", "改造策略"],
    )


def test_is_renovation_scenario_from_brief() -> None:
    assert is_renovation_scenario(brief=_renovation_brief()) is True


def test_is_renovation_scenario_false_for_culture() -> None:
    brief = PresentationBrief(
        project_id=uuid4(),
        presentation_id=uuid4(),
        title="文化名村",
        audience="文旅局",
        purpose="文化名村保护提升",
        core_message="活态传承",
    )
    assert is_renovation_scenario(brief=brief) is False


def test_issue_map_from_draft_preserves_links() -> None:
    project_id = uuid4()
    draft = RenovationIssueMapDraft(
        building_summary="测试建筑",
        evidence_items=[],
        issues=[
            RenovationIssueDraft(
                id="i1",
                category="circulation",
                problem_statement="流线问题",
                linked_evidence_ids=["ev1"],
            )
        ],
        strategies=[
            RenovationStrategyDraft(
                id="s1",
                title="交通优化",
                approach="重组流线",
                linked_issue_ids=["i1"],
            )
        ],
    )
    plan = issue_map_from_draft(draft, project_id=project_id)
    assert plan.issues[0].linked_evidence_ids == ["ev1"]
    assert plan.strategies[0].linked_issue_ids == ["i1"]


def test_validate_issue_map_flags_unlinked_strategy() -> None:
    plan = issue_map_from_draft(
        RenovationIssueMapDraft(
            building_summary="建筑",
            strategies=[RenovationStrategyDraft(id="s1", title="空策略", approach="待定")],
        ),
        project_id=uuid4(),
    )
    issues = validate_issue_map(plan)
    assert any("策略未关联问题" in issue for issue in issues)


def test_issue_map_fallback_from_brief_has_closed_loop() -> None:
    brief = _renovation_brief()
    plan = issue_map_fallback_from_brief(brief, project_id=brief.project_id)
    assert plan.evidence_items
    assert plan.issues
    assert plan.strategies
    assert plan.issues[0].linked_evidence_ids
    assert plan.strategies[0].linked_issue_ids
