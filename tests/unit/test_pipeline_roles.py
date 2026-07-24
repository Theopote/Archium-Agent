"""Tests for PipelineRole vocabulary and E2E stage alignment."""

from __future__ import annotations

from archium.domain.enums import PipelineRole, ReviewLayer, WorkflowStep
from archium.domain.pipeline_role_mapping import (
    E2E_PIPELINE_STAGE_TO_ROLE,
    PRODUCT_AGENT_ROLES,
    pipeline_role_for_e2e_stage,
    pipeline_role_for_review_layer,
    pipeline_role_for_workflow_step,
    pipeline_roles_for_e2e_stages,
    product_agent_roles_for_e2e_stages,
    to_product_agent_role,
)
from archium.domain.project_acceptance import Phase7ProjectProfile

from tests.e2e.real_projects.phase7_loader import load_phase7_project


def test_e2e_stage_mapping_covers_phase7_profiles() -> None:
    for project_id in ("cultural_village_001", "renovation_001"):
        profile = load_phase7_project(project_id).profile
        for stage in profile.required_pipeline_stages:
            assert stage in profile.stage_pipeline_roles
            assert profile.stage_pipeline_roles[stage] == E2E_PIPELINE_STAGE_TO_ROLE[stage]
        assert profile.required_pipeline_roles == pipeline_roles_for_e2e_stages(
            profile.required_pipeline_stages
        )


def test_phase7_profile_backfills_roles_from_stages_only() -> None:
    profile = Phase7ProjectProfile.model_validate(
        {
            "id": "test",
            "scenario": "cultural_village",
            "name": "t",
            "project_type": "culture",
            "target_slide_count": 20,
            "required_pipeline_stages": ["ingest", "layout", "pptx_export"],
        }
    )
    assert profile.stage_pipeline_roles["ingest"] == PipelineRole.RESEARCH
    assert profile.stage_pipeline_roles["layout"] == PipelineRole.LAYOUT
    assert profile.required_pipeline_roles == [
        PipelineRole.RESEARCH,
        PipelineRole.LAYOUT,
        PipelineRole.RENDER,
    ]


def test_workflow_step_and_review_layer_mappings() -> None:
    assert pipeline_role_for_workflow_step(WorkflowStep.EXTRACT_FACTS) == PipelineRole.RESEARCH
    assert pipeline_role_for_workflow_step(WorkflowStep.VISUAL_RENDER) == PipelineRole.RENDER
    assert pipeline_role_for_review_layer(ReviewLayer.ARCHITECTURAL) == PipelineRole.ARCHITECTURE
    assert pipeline_role_for_e2e_stage("unknown_stage") is None


def test_product_agent_roster_is_fixed_six_seats() -> None:
    assert PRODUCT_AGENT_ROLES == (
        PipelineRole.RESEARCH,
        PipelineRole.PLANNING,
        PipelineRole.NARRATIVE,
        PipelineRole.VISUAL,
        PipelineRole.RENDER,
        PipelineRole.CRITIC,
    )
    assert to_product_agent_role(PipelineRole.LAYOUT) == PipelineRole.VISUAL
    assert to_product_agent_role(PipelineRole.COMPOSITION) == PipelineRole.VISUAL
    assert to_product_agent_role(PipelineRole.ARCHITECTURE) == PipelineRole.VISUAL
    assert to_product_agent_role(PipelineRole.PLANNING) == PipelineRole.PLANNING
    assert product_agent_roles_for_e2e_stages(
        ["ingest", "deck_composition", "layout", "pptx_export"]
    ) == [
        PipelineRole.RESEARCH,
        PipelineRole.VISUAL,
        PipelineRole.RENDER,
    ]


def test_planning_workflow_steps_map_to_planning_seat() -> None:
    assert (
        pipeline_role_for_workflow_step(WorkflowStep.PLANNING_ANALYZE_TASK)
        == PipelineRole.PLANNING
    )
