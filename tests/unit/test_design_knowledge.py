"""Unit tests for DesignKnowledge mapping and prompt injection."""

from __future__ import annotations

from archium.application.design_knowledge_context import format_design_knowledge_block
from archium.application.design_knowledge_mapping import design_knowledge_from_finding
from archium.domain.design_knowledge import DesignKnowledge
from archium.domain.enums import InformationOrigin, InformationReliability, ProjectOriginMode
from archium.domain.project import Project
from archium.domain.project_knowledge import ProjectKnowledgeItem
from archium.infrastructure.database.repositories import (
    ProjectKnowledgeRepository,
    ProjectRepository,
)
from archium.infrastructure.llm.research_schemas import (
    ResearchFindingDraft,
    ResearchSourceDraft,
)
from archium.prompts.concept_direction import build_exploration_direction_user_prompt


def test_design_knowledge_from_structured_fields() -> None:
    finding = ResearchFindingDraft(
        topic="山地公共空间",
        summary="摘要",
        problem="山地乡镇缺少可停留公共核",
        insight="公共性沿台地展开",
        strategy="台地层级组织公共性",
        principle="台地层级",
        spatial_translation="台地院落",
        material_strategy="石材",
        project_link="适用本项目",
        applicability="坡地乡镇",
        precedent_ref="case:terrace_settlement",
        suggested_sources=[
            ResearchSourceDraft(title="研究A", url="https://example.org/a"),
        ],
    )
    knowledge = design_knowledge_from_finding(finding)
    assert knowledge.has_substance
    assert knowledge.problem.startswith("山地乡镇")
    assert knowledge.strategy.startswith("台地层级组织")
    assert knowledge.principle == "台地层级"
    assert knowledge.precedent_ref == "case:terrace_settlement"
    assert "研究A" in knowledge.evidence


def test_design_knowledge_from_labeled_key_points() -> None:
    finding = ResearchFindingDraft(
        topic="x",
        summary="摘要即洞察",
        key_points=[
            "问题：公共空间缺失",
            "策略：内向聚合",
            "原则：内向聚合",
            "空间：围合院落",
            "适用：关中",
            "先例：case:rural_courtyard_type",
        ],
        relevance="项目可用",
    )
    knowledge = design_knowledge_from_finding(finding)
    assert knowledge.problem == "公共空间缺失"
    assert knowledge.strategy == "内向聚合"
    assert knowledge.principle == "内向聚合"
    assert knowledge.spatial_translation == "围合院落"
    assert knowledge.applicability == "关中"
    assert knowledge.project_link == "项目可用"
    assert knowledge.precedent_ref == "case:rural_courtyard_type"


def test_format_design_knowledge_block_for_concept(db_session) -> None:
    project = ProjectRepository(db_session).create(
        Project(name="测试", origin_mode=ProjectOriginMode.CONCEPT_EXPLORATION)
    )
    ProjectKnowledgeRepository(db_session).create(
        ProjectKnowledgeItem(
            project_id=project.id,
            statement="台地公共性",
            origin=InformationOrigin.PUBLIC_RESEARCH,
            reliability=InformationReliability.UNVERIFIED,
            design_knowledge=DesignKnowledge(
                topic="山地",
                insight="公共性沿台地",
                principle="台地层级",
                spatial_translation="台地院落",
                project_link="本项目可用",
            ),
        )
    )
    db_session.commit()
    block = format_design_knowledge_block(db_session, project.id)
    assert "DesignKnowledge" in block
    assert "台地层级" in block
    prompt = build_exploration_direction_user_prompt(
        project_name=project.name,
        idea_text="山地文化中心",
        count=2,
        design_knowledge_block=block,
    )
    assert "已沉淀设计知识" in prompt
    assert "spatial_strategy" in prompt
