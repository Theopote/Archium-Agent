"""Map E2E acceptance stages and review layers to :class:`PipelineRole`."""

from __future__ import annotations

from archium.domain.enums import PipelineRole, ReviewLayer, WorkflowStep

# E2E Phase 7 acceptance stage → logical role (see project_profile.json).
E2E_PIPELINE_STAGE_TO_ROLE: dict[str, PipelineRole] = {
    "ingest": PipelineRole.RESEARCH,
    "research": PipelineRole.RESEARCH,
    "outline_confirmation": PipelineRole.NARRATIVE,
    "slides": PipelineRole.NARRATIVE,
    "deck_composition": PipelineRole.COMPOSITION,
    "layout": PipelineRole.LAYOUT,
    "pptx_export": PipelineRole.RENDER,
    "studio_edit": PipelineRole.RENDER,
    "human_review": PipelineRole.CRITIC,
    "final_acceptance": PipelineRole.CRITIC,
}

_PIPELINE_ROLE_LABELS_ZH: dict[PipelineRole, str] = {
    PipelineRole.RESEARCH: "Research · 事实与来源",
    PipelineRole.NARRATIVE: "Narrative · 大纲与叙事",
    PipelineRole.ARCHITECTURE: "Architecture · 建筑语义",
    PipelineRole.COMPOSITION: "Composition · Deck 节奏",
    PipelineRole.LAYOUT: "Layout · 页面版式",
    PipelineRole.RENDER: "Render · 导出与场景",
    PipelineRole.CRITIC: "Critic · 问题发现",
}

_REVIEW_LAYER_TO_ROLE: dict[ReviewLayer, PipelineRole] = {
    ReviewLayer.CONTENT: PipelineRole.CRITIC,
    ReviewLayer.EVIDENCE: PipelineRole.CRITIC,
    ReviewLayer.ARCHITECTURAL: PipelineRole.ARCHITECTURE,
    ReviewLayer.LAYOUT: PipelineRole.LAYOUT,
    ReviewLayer.SEMANTIC: PipelineRole.CRITIC,
}

_WORKFLOW_STEP_TO_ROLE: dict[WorkflowStep, PipelineRole] = {
    WorkflowStep.RETRIEVE_CONTEXT: PipelineRole.RESEARCH,
    WorkflowStep.EXTRACT_FACTS: PipelineRole.RESEARCH,
    WorkflowStep.VALIDATE_FACTS: PipelineRole.RESEARCH,
    WorkflowStep.RESOLVE_CITATIONS: PipelineRole.RESEARCH,
    WorkflowStep.MATCH_ASSETS: PipelineRole.RESEARCH,
    WorkflowStep.BRIEF: PipelineRole.NARRATIVE,
    WorkflowStep.STORYLINE: PipelineRole.NARRATIVE,
    WorkflowStep.OUTLINE: PipelineRole.NARRATIVE,
    WorkflowStep.SLIDES: PipelineRole.NARRATIVE,
    WorkflowStep.CULTURAL_NARRATIVE: PipelineRole.NARRATIVE,
    WorkflowStep.RENOVATION_ISSUE_MAP: PipelineRole.ARCHITECTURE,
    WorkflowStep.CONTENT_REVIEW: PipelineRole.CRITIC,
    WorkflowStep.EVIDENCE_REVIEW: PipelineRole.CRITIC,
    WorkflowStep.ARCHITECTURAL_REVIEW: PipelineRole.CRITIC,
    WorkflowStep.LAYOUT_REVIEW: PipelineRole.CRITIC,
    WorkflowStep.REPAIR_SLIDES: PipelineRole.CRITIC,
    WorkflowStep.EXPORT: PipelineRole.RENDER,
    WorkflowStep.PRESENTATION_SPEC: PipelineRole.RENDER,
    WorkflowStep.MARP: PipelineRole.RENDER,
    WorkflowStep.VISUAL_GENERATE_ART_DIRECTION: PipelineRole.COMPOSITION,
    WorkflowStep.VISUAL_GENERATE_INTENTS: PipelineRole.COMPOSITION,
    WorkflowStep.VISUAL_GENERATE_DECK_COMPOSITION: PipelineRole.COMPOSITION,
    WorkflowStep.VISUAL_GENERATE_LAYOUT_CANDIDATES: PipelineRole.LAYOUT,
    WorkflowStep.VISUAL_SELECT_LAYOUTS: PipelineRole.LAYOUT,
    WorkflowStep.VISUAL_VALIDATE_LAYOUTS: PipelineRole.LAYOUT,
    WorkflowStep.VISUAL_REPAIR_LAYOUTS: PipelineRole.LAYOUT,
    WorkflowStep.VISUAL_RENDER: PipelineRole.RENDER,
    WorkflowStep.VISUAL_CRITIQUE: PipelineRole.CRITIC,
}


def pipeline_role_label(role: PipelineRole) -> str:
    """Short bilingual label for UI captions."""
    return _PIPELINE_ROLE_LABELS_ZH.get(role, role.value)


def pipeline_role_for_e2e_stage(stage: str) -> PipelineRole | None:
    return E2E_PIPELINE_STAGE_TO_ROLE.get(stage.strip().lower())


def pipeline_roles_for_e2e_stages(stages: list[str]) -> list[PipelineRole]:
    """Ordered unique roles required by an E2E stage list."""
    seen: set[PipelineRole] = set()
    ordered: list[PipelineRole] = []
    for stage in stages:
        role = pipeline_role_for_e2e_stage(stage)
        if role is None or role in seen:
            continue
        seen.add(role)
        ordered.append(role)
    return ordered


def default_stage_pipeline_roles(stages: list[str]) -> dict[str, PipelineRole]:
    """Build stage → role map; unknown stages default to NARRATIVE."""
    result: dict[str, PipelineRole] = {}
    for stage in stages:
        key = stage.strip().lower()
        result[key] = pipeline_role_for_e2e_stage(key) or PipelineRole.NARRATIVE
    return result


def pipeline_role_for_review_layer(layer: ReviewLayer) -> PipelineRole:
    return _REVIEW_LAYER_TO_ROLE.get(layer, PipelineRole.CRITIC)


def pipeline_role_for_workflow_step(step: WorkflowStep) -> PipelineRole | None:
    return _WORKFLOW_STEP_TO_ROLE.get(step)
