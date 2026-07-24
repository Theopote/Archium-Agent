"""Integration tests for partial-knowledge projects (Playbook F backbone).

Scenario: user describes a renovation with minimal uploads — not pure concept,
not a full existing-project dossier. Archium should assess context, suggest
clarify/explore (not materials-only), and allow concept exploration → Mission.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from archium.application.context_intelligence_service import ContextIntelligenceService
from archium.application.exploration_service import ExplorationService
from archium.application.ingestion_service import IngestionService
from archium.application.project_context_builder import build_project_context
from archium.application.workspace_mode_service import WorkspaceModeService
from archium.domain.context.lifecycle_stage import ProjectLifecycleStage
from archium.domain.context.recommended_workflow import RecommendedWorkflow
from archium.domain.document import DocumentChunk, SourceDocument
from archium.domain.enums import (
    ConceptDirectionStatus,
    DocumentType,
    ExplorationSessionStatus,
    ProcessingStatus,
    ProjectOriginMode,
    VerificationStatus,
)
from archium.domain.fact import ProjectFact
from archium.domain.intent.next_best_action import NextBestActionType
from archium.domain.project import Project
from archium.infrastructure.database.repositories import (
    DocumentRepository,
    FactRepository,
    ProjectRepository,
)
from archium.infrastructure.llm.concept_direction_schemas import (
    ConceptDirectionBatchDraft,
    ConceptDirectionDraft,
    ConceptVisualPromptDraft,
)
from archium.infrastructure.llm.context_intelligence_schemas import (
    ContextAssessmentDraft,
    NextBestActionDraft,
)
from archium.infrastructure.llm.idea_seed_schemas import IdeaSeedDraft
from archium.infrastructure.llm.mission_schemas import (
    DesignIntentDraft,
    MissionGenerationDraft,
)

from tests.fixtures.sample_files import create_sample_docx

PARTIAL_KNOWLEDGE_PROMPT = (
    "西安市某医院老院区改造，手头有一张老门诊楼照片、"
    "地址和一份旧院区介绍，甲方还没说清功能分区。"
)


@pytest.fixture
def partial_project(db_session) -> Project:
    return ProjectRepository(db_session).create(
        Project(
            name="西安某医院老院区改造",
            description=PARTIAL_KNOWLEDGE_PROMPT,
        )
    )


def _seed_partial_materials(
    db_session,
    project_id,
    tmp_path,
    *,
    ingestion_service: IngestionService | None = None,
) -> None:
    FactRepository(db_session).create(
        ProjectFact(
            project_id=project_id,
            key="location",
            label="地点",
            value="西安",
            verification_status=VerificationStatus.USER_CONFIRMED,
        )
    )
    docx = create_sample_docx(
        tmp_path / "旧院区介绍.docx",
        heading="老院区概况",
        body="现状门诊楼建于1998年，南北向布局，需保留部分历史立面。",
    )
    if ingestion_service is not None:
        ingestion_service.import_file(project_id, docx)
    else:
        doc = DocumentRepository(db_session).create_document(
            SourceDocument(
                project_id=project_id,
                filename="旧院区介绍.docx",
                original_path=str(docx),
                stored_path=str(docx),
                file_type=DocumentType.DOCX,
                file_hash="b" * 64,
                size_bytes=docx.stat().st_size,
                processing_status=ProcessingStatus.COMPLETED,
            )
        )
        DocumentRepository(db_session).create_chunk(
            DocumentChunk(
                document_id=doc.id,
                project_id=project_id,
                content="现状门诊楼建于1998年，南北向布局，需保留部分历史立面。",
                chunk_index=0,
                page_number=1,
                content_type="text",
            )
        )
    db_session.commit()


def test_partial_knowledge_assessment_routes_by_context(
    db_session,
    partial_project,
    tmp_path,
) -> None:
    _seed_partial_materials(db_session, partial_project.id, tmp_path)
    llm = MagicMock()
    llm.generate_structured.return_value = ContextAssessmentDraft(
        completeness_score=0.34,
        maturity_stage="design_analysis",
        evidence_ratio=0.22,
        assumption_ratio=0.72,
        known={"location": "西安", "type": "医院改造"},
        unknown=["功能分区", "规模", "投资"],
        missing_information=["功能分区", "规模"],
        suggested_origin_mode="existing_project",
        understanding_summary="部分资料：有地点与旧楼背景，仍缺功能与规模。",
        actions=[
            NextBestActionDraft(
                action="ask",
                reason="甲方尚未说清功能分区",
                question="本次改造优先解决哪些科室或流线问题？",
                priority=0,
            ),
            NextBestActionDraft(
                action="explore_directions",
                reason="在已知约束内并行推演改造策略",
                priority=1,
            ),
            NextBestActionDraft(
                action="upload_materials",
                reason="可继续补充图纸与照片",
                priority=2,
            ),
        ],
    )
    service = ContextIntelligenceService(db_session, llm)
    result = service.assess_and_persist(partial_project.id, PARTIAL_KNOWLEDGE_PROMPT)

    assert result.project_context is not None
    assert result.suggested_origin_mode == ProjectOriginMode.CONCEPT_EXPLORATION
    assert result.knowledge_state.completeness_score < 0.5
    assert result.knowledge_state.completeness_score >= 0.2
    assert result.project_context.lifecycle_stage in {
        ProjectLifecycleStage.RESEARCH,
        ProjectLifecycleStage.CONCEPT,
    }
    assert result.project_context.recommended_workflow in {
        RecommendedWorkflow.MISSION,
        RecommendedWorkflow.EXPLORE,
    }
    assert result.actions[0].action in {
        NextBestActionType.ASK,
        NextBestActionType.EXPLORE_DIRECTIONS,
    }

    refreshed = ProjectRepository(db_session).get_by_id(partial_project.id)
    assert refreshed is not None
    assert refreshed.origin_mode == ProjectOriginMode.CONCEPT_EXPLORATION

    ctx = build_project_context(db_session, refreshed)
    assert ctx is not None
    workspace = WorkspaceModeService(db_session)
    mode = workspace.resolve_mode(partial_project.id)
    primary = workspace.resolve_primary_page_key(partial_project.id)
    assert mode.value == "concept_exploration"
    assert primary == "project-mission"


def test_partial_knowledge_rule_fallback_still_clarifies_first(
    db_session,
    partial_project,
    tmp_path,
) -> None:
    _seed_partial_materials(db_session, partial_project.id, tmp_path)
    llm = MagicMock()
    llm.generate_structured.side_effect = RuntimeError("llm down")
    service = ContextIntelligenceService(db_session, llm)
    result = service.assess_and_persist(partial_project.id, PARTIAL_KNOWLEDGE_PROMPT)

    assert result.warnings
    assert result.actions
    assert result.actions[0].action in {
        NextBestActionType.ASK,
        NextBestActionType.GENERATE_MISSION,
        NextBestActionType.EXPLORE_DIRECTIONS,
    }
    assert result.knowledge_state.completeness_score < 0.6


def test_partial_knowledge_exploration_to_mission_with_structured_directions(
    db_session,
    partial_project,
    tmp_path,
    test_settings,
) -> None:
    ingestion = IngestionService(db_session, settings=test_settings)
    _seed_partial_materials(
        db_session,
        partial_project.id,
        tmp_path,
        ingestion_service=ingestion,
    )

    assess_llm = MagicMock()
    assess_llm.generate_structured.return_value = ContextAssessmentDraft(
        completeness_score=0.32,
        maturity_stage="design_analysis",
        evidence_ratio=0.2,
        assumption_ratio=0.75,
        known={"location": "西安"},
        unknown=["功能分区"],
        missing_information=["功能分区"],
        suggested_origin_mode="existing_project",
        understanding_summary="部分资料改造任务。",
        actions=[
            NextBestActionDraft(action="explore_directions", reason="推演", priority=0),
        ],
    )
    ContextIntelligenceService(db_session, assess_llm).assess_and_persist(
        partial_project.id,
        PARTIAL_KNOWLEDGE_PROMPT,
    )

    explore_llm = MagicMock()
    explore_llm.generate_structured.side_effect = [
        IdeaSeedDraft(
            theme="医院老院区再生",
            inspiration="在有限资料下保留历史与更新流线",
            keywords=["改造", "老院区", "西安"],
            imagination_level="moderate",
        ),
        ConceptDirectionBatchDraft(
            directions=[
                ConceptDirectionDraft(
                    title="微创更新",
                    summary="保留立面与结构，局部加建",
                    theme="最小干预",
                    spatial_idea="沿既有轴线插入新核",
                    spatial_strategy="保留南北主轴线，点状加建",
                    formal_language="新旧并置，克制体量",
                    material_strategy="保留砖墙，局部玻璃连廊",
                    reference_dna=["医院改扩建类型", "工业遗产式更新"],
                    visual_prompt=ConceptVisualPromptDraft(
                        image_prompt="hospital campus renovation axonometric, preserved brick facade",
                        camera="architectural axonometric",
                        style="concept sketch",
                    ),
                    experience_focus="医护与患者流线清晰",
                    differentiator="在资料有限时仍可做策略比较",
                    open_questions=["功能分区？"],
                    risks=["结构鉴定未做"],
                ),
                ConceptDirectionDraft(
                    title="片区重组",
                    summary="重新组织入口与门诊流线",
                    theme="流线重组",
                    spatial_idea="新入口广场 + 内部连廊",
                    spatial_strategy="入口外移，内部环形流线",
                    formal_language="清晰几何与开放灰空间",
                    material_strategy="浅色石材与金属雨棚",
                    reference_dna=["当代医疗建筑入口策略"],
                    visual_prompt=ConceptVisualPromptDraft(
                        image_prompt="hospital entrance plaza reorganization concept",
                        camera="eye-level",
                        style="soft atmosphere",
                    ),
                    experience_focus="患者到达体验",
                    differentiator="从城市界面重新定义院区",
                    open_questions=["市政退线？"],
                    risks=["拆迁范围未定"],
                ),
            ]
        ),
        MissionGenerationDraft(
            title="西安某医院老院区改造",
            task_statement="在部分资料条件下明确改造策略与待澄清问题",
            design_intent=DesignIntentDraft(
                theme="最小干预",
                problem_statement="如何在资料不完整时推进改造讨论？",
                target_users=["医护", "患者"],
                desired_experience="流线清晰",
            ),
            assumptions=[],
            clarifying_questions=[],
            knowledge_gaps=[],
        ),
    ]

    exploration_service = ExplorationService(db_session, explore_llm)
    exploration = exploration_service.start_session(
        partial_project.id,
        PARTIAL_KNOWLEDGE_PROMPT,
    ).exploration
    assert exploration.idea_seed is not None

    generated = exploration_service.generate_directions(exploration.id)
    assert len(generated.directions) >= 2
    first = generated.directions[0]
    assert first.spatial_strategy
    assert first.visual_prompt is not None
    assert first.visual_prompt.image_prompt

    selected = exploration_service.select_direction(first.id)
    assert selected.direction.status == ConceptDirectionStatus.SELECTED

    committed = exploration_service.commit_to_mission(exploration.id)
    assert committed.exploration.status == ExplorationSessionStatus.COMMITTED
    assert committed.mission.design_intent is not None
    assert committed.direction.mission_id == committed.mission.id

    ctx = build_project_context(db_session, partial_project.id)
    assert ctx is not None
    assert ctx.knowledge_state.completeness_score < 0.55
