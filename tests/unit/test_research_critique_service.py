"""Unit tests for Research Critic."""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

from archium.application.review.research_critique_service import ResearchCritiqueService
from archium.config.settings import Settings
from archium.domain.design_knowledge import DesignKnowledge
from archium.domain.enums import InformationOrigin, InformationReliability
from archium.domain.project_knowledge import ProjectKnowledgeItem, SourceCitation
from archium.domain.research_critique import (
    ResearchCritiqueIssueKind,
    ResearchCritiqueVerdict,
)


def _item(
    *,
    statement: str,
    citations: bool = True,
    knowledge: DesignKnowledge | None = None,
) -> ProjectKnowledgeItem:
    cites = []
    if citations:
        cites = [
            SourceCitation(
                url="https://example.org/r",
                source_title="研究来源",
            )
        ]
    return ProjectKnowledgeItem(
        project_id=uuid4(),
        statement=statement,
        origin=InformationOrigin.PUBLIC_RESEARCH,
        reliability=InformationReliability.UNVERIFIED,
        source_citations=cites,
        design_knowledge=knowledge,
        category="research",
    )


def test_rules_flag_missing_structure_and_citations() -> None:
    service = ResearchCritiqueService(
        MagicMock(),
        None,
        settings=Settings(_env_file=None, research_critique_mode="warn"),
    )
    report = service.critique_items(
        [
            _item(
                statement="背景综述：很多案例简介与概况",
                citations=False,
                knowledge=None,
            )
        ],
        design_context="山地文化中心",
        use_llm=False,
    )
    assert report.verdict == ResearchCritiqueVerdict.WEAK
    assert report.validity < 0.6
    assert report.design_relevance < 0.55
    kinds = {issue.kind for issue in report.issues}
    assert ResearchCritiqueIssueKind.WEAK_CITATION in kinds
    assert (
        ResearchCritiqueIssueKind.MISSING_STRUCTURE in kinds
        or ResearchCritiqueIssueKind.BACKGROUND_ONLY in kinds
    )


def test_structured_design_knowledge_scores_higher() -> None:
    service = ResearchCritiqueService(
        MagicMock(),
        None,
        settings=Settings(_env_file=None),
    )
    report = service.critique_items(
        [
            _item(
                statement="台地公共性",
                citations=True,
                knowledge=DesignKnowledge(
                    topic="山地",
                    insight="公共性应沿台地展开",
                    principle="台地层级组织公共空间",
                    spatial_translation="台地院落 + 入口广场",
                    project_link="适用于本项目",
                    applicability="坡地乡镇中小体量",
                    evidence=["来源A"],
                ),
            )
        ],
        use_llm=False,
    )
    assert report.verdict in {
        ResearchCritiqueVerdict.ACCEPT,
        ResearchCritiqueVerdict.CAUTION,
    }
    assert report.design_relevance >= 0.6
    assert report.validity >= 0.7


def test_over_analogy_tokens_flagged() -> None:
    service = ResearchCritiqueService(MagicMock(), None)
    report = service.critique_items(
        [
            _item(
                statement="该瑞士温泉方案完全适用本地山地文化中心，必须采用同样石材表情",
                citations=True,
                knowledge=DesignKnowledge(
                    topic="Vals",
                    insight="嵌入山体",
                    principle="路径体验",
                    spatial_translation="洞穴路径",
                ),
            )
        ],
        use_llm=False,
    )
    assert any(
        issue.kind == ResearchCritiqueIssueKind.OVER_ANALOGY for issue in report.issues
    )
