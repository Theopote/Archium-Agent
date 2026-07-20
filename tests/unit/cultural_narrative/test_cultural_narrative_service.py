"""Unit tests for cultural narrative planning."""

from __future__ import annotations

from uuid import uuid4

from archium.application.cultural_narrative_service import (
    is_cultural_village_scenario,
    narrative_fallback_from_brief,
    narrative_from_draft,
    validate_narrative,
)
from archium.domain.enums import ProjectType
from archium.domain.presentation import PresentationBrief
from archium.domain.project import Project
from archium.infrastructure.llm.presentation_schemas import (
    CommunicationThemeDraft,
    CulturalNarrativePlanDraft,
)


def _cultural_brief() -> PresentationBrief:
    return PresentationBrief(
        project_id=uuid4(),
        presentation_id=uuid4(),
        title="文化名村汇报",
        audience="文旅局",
        purpose="文化名村保护提升",
        core_message="活态传承与合理更新",
        required_sections=["历史沿革", "传播品牌"],
    )


def test_is_cultural_village_scenario_from_brief() -> None:
    assert is_cultural_village_scenario(brief=_cultural_brief()) is True


def test_is_cultural_village_scenario_from_culture_project() -> None:
    project = Project(name="古村", project_type=ProjectType.CULTURE)
    assert is_cultural_village_scenario(project=project) is True


def test_narrative_from_draft_builds_linked_theme() -> None:
    project_id = uuid4()
    draft = CulturalNarrativePlanDraft(
        central_story="测试故事",
        identity_keywords=["水乡"],
        communication_themes=[
            CommunicationThemeDraft(
                id="t1",
                theme="活态传承",
                linked_places=["place1"],
            )
        ],
    )
    plan = narrative_from_draft(draft, project_id=project_id)
    assert plan.project_id == project_id
    assert plan.central_story == "测试故事"
    assert plan.communication_themes[0].linked_places == ["place1"]


def test_validate_narrative_flags_unlinked_theme() -> None:
    plan = narrative_from_draft(
        CulturalNarrativePlanDraft(
            central_story="故事",
            communication_themes=[CommunicationThemeDraft(id="t1", theme="空主题")],
        ),
        project_id=uuid4(),
    )
    issues = validate_narrative(plan)
    assert any("传播主题未关联" in issue for issue in issues)


def test_narrative_fallback_from_brief() -> None:
    brief = _cultural_brief()
    plan = narrative_fallback_from_brief(brief, project_id=brief.project_id)
    assert plan.central_story
    assert plan.unsupported_claims
