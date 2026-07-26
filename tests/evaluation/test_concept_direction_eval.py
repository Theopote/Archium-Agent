"""Evaluation: ConceptDirection / DesignIntent contracts for mountain cultural center.

Product scenario (not an Agent class): input idea → directions must expose
spatial strategy, formal language, risks; committed Mission DesignIntent must
carry social_background.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from archium.application.exploration_service import ExplorationService
from archium.domain.enums import ProjectOriginMode
from archium.domain.project import Project
from archium.infrastructure.database.repositories import ProjectRepository
from archium.infrastructure.llm.concept_direction_schemas import (
    ConceptDirectionBatchDraft,
    ConceptDirectionDraft,
    ConceptVisualPromptDraft,
)
from archium.infrastructure.llm.context_intelligence_schemas import (
    ContextAssessmentDraft,
    NextBestActionDraft,
)
from archium.infrastructure.llm.design_critique_schemas import (
    DesignCritiqueDraft,
    DesignCritiqueItemDraft,
)
from archium.infrastructure.llm.idea_seed_schemas import IdeaSeedDraft
from archium.infrastructure.llm.mission_schemas import (
    AssumptionDraft,
    DesignIntentDraft,
    MissionGenerationDraft,
)

from tests.evaluation.assertions import (
    assert_concept_direction_contract,
    assert_design_intent_social_background,
)

SCENARIO_IDEA = "山地文化中心"


@pytest.fixture
def mountain_project(db_session):
    return ProjectRepository(db_session).create(
        Project(
            name="山地文化中心",
            description="评价场景：山地文化中心概念探索",
            origin_mode=ProjectOriginMode.CONCEPT_EXPLORATION,
        )
    )


def _idea_seed() -> IdeaSeedDraft:
    return IdeaSeedDraft(
        theme="山地公共文化",
        inspiration="山地聚落与文化外溢",
        keywords=["山地", "文化中心", "台地", "社区"],
        imagination_level="open",
    )


def _direction_batch() -> ConceptDirectionBatchDraft:
    return ConceptDirectionBatchDraft(
        directions=[
            ConceptDirectionDraft(
                title="台地聚落文化核",
                summary="沿山地台地展开的公共文化群落",
                theme="台地生活",
                spatial_idea="分散院落 + 共享庭院",
                spatial_strategy="台地层级组织公共空间与观景轴线",
                formal_language="低平体量，连续屋面，嵌入坡地",
                material_strategy="本地石材与木构",
                reference_dna=["山地聚落类型学"],
                visual_prompt=ConceptVisualPromptDraft(
                    image_prompt="mountain cultural center on terraces",
                    camera="axonometric",
                    style="concept sketch",
                ),
                experience_focus="村民日常与访客穿行",
                differentiator="以地貌组织公共性",
                open_questions=["规模上限？"],
                risks=["运营负担", "坡地无障碍通行"],
            ),
            ConceptDirectionDraft(
                title="山脊驿站",
                summary="轻量驿站串联山脊景观",
                theme="轻介入",
                spatial_idea="线性廊道与眺望点",
                spatial_strategy="沿等高线的线性公共带",
                formal_language="轻钢木构，通透界面",
                material_strategy="木构与玻璃",
                experience_focus="路过停留",
                differentiator="最小建筑量",
                open_questions=["常驻功能？"],
                risks=["辨识度不足", "气候暴露"],
            ),
        ]
    )


def _critique() -> DesignCritiqueDraft:
    return DesignCritiqueDraft(
        verdict="caution",
        summary="方向可继续，建议补场地证据",
        strengths=[
            DesignCritiqueItemDraft(
                text="台地策略回应山地地貌",
                challenge="problem_fit",
            )
        ],
        weaknesses=[
            DesignCritiqueItemDraft(
                text="社会服务对象仍偏笼统",
                challenge="why",
                severity="medium",
            )
        ],
        missing_evidence=[
            DesignCritiqueItemDraft(
                text="缺具体场地高程与可达性依据",
                challenge="evidence",
                severity="high",
            )
        ],
        alternative_directions=[
            DesignCritiqueItemDraft(
                text="可先以社区礼堂+外溢广场为问题驱动，再定台地形式",
                challenge="alternative",
            )
        ],
        form_only_risk=False,
    )


def _ks() -> ContextAssessmentDraft:
    return ContextAssessmentDraft(
        completeness_score=0.35,
        maturity_stage="concept_formation",
        evidence_ratio=0.2,
        assumption_ratio=0.7,
        known={"type": "文化中心", "location": "山地"},
        unknown=["用地红线"],
        missing_information=["用地红线"],
        suggested_origin_mode="concept_exploration",
        understanding_summary="山地文化中心概念探索中。",
        actions=[
            NextBestActionDraft(
                action="explore_directions",
                reason="继续方向比较",
                priority=0,
            ),
        ],
    )


def _mission() -> MissionGenerationDraft:
    return MissionGenerationDraft(
        title="山地文化中心概念探索",
        task_statement="探索嵌入山地聚落的小型文化中心",
        design_intent=DesignIntentDraft(
            theme="山地公共文化",
            problem_statement="山地聚落公共服务缺口与文化外溢需求如何用建筑回应？",
            social_background="山地乡镇人口外流、公共文化设施薄弱、在地认同待强化",
            cultural_context="山地聚落与台地农耕景观",
            target_users=["村民", "访客"],
            desired_experience="在地认同与开放交流",
            core_questions=["如何让建筑成为社区生活的延伸？"],
            research_needed=["山地文化建筑案例"],
            working_assumptions=["初期规模待确认"],
        ),
        assumptions=[
            AssumptionDraft(
                statement="假定位于中国南方山地乡镇",
                reason="用户未提供精确地点",
                requires_confirmation=True,
            )
        ],
        clarifying_questions=[],
        knowledge_gaps=[],
    )


def test_mountain_cultural_center_directions_meet_concept_contract(
    db_session,
    mountain_project,
) -> None:
    """Eval: 山地文化中心 → 空间策略 / 形式语言 / 风险 非空。"""
    llm = MagicMock()
    llm.generate_structured.side_effect = [
        _idea_seed(),
        _direction_batch(),
        _critique(),
        _ks(),
        _mission(),
        _ks(),
    ]
    service = ExplorationService(db_session, llm)

    started = service.start_session(mountain_project.id, SCENARIO_IDEA)
    assert SCENARIO_IDEA in (started.exploration.idea_seed.raw_input if started.exploration.idea_seed else "")

    generated = service.generate_directions(started.exploration.id, count=2)
    assert len(generated.directions) >= 2
    for direction in generated.directions:
        assert_concept_direction_contract(direction)

    selected = service.select_direction(generated.directions[0].id)
    assert_concept_direction_contract(selected.direction)

    committed = service.commit_to_mission(started.exploration.id)
    assert_design_intent_social_background(committed.mission.design_intent)
