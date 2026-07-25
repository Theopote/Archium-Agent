"""Project context intelligence layer — assess knowledge and route next steps."""

from archium.application.context.context_analyzer import ContextAnalyzer
from archium.application.context.knowledge_assessor import KnowledgeAssessor
from archium.application.context.knowledge_claim_index import (
    merge_claim_index_into_state,
    refresh_claim_index_only,
)
from archium.application.context.knowledge_reassess import (
    ReassessMode,
    best_effort_reassess_knowledge,
    classify_reassess_mode,
)
from archium.application.context.knowledge_vector_policy import (
    actions_for_presentation_entry,
    actions_from_knowledge_vector,
)
from archium.application.context.nba_action_executor import (
    NbaActionExecutor,
    NbaExecutionResult,
    nba_execute_label,
)
from archium.application.context.next_action_selector import (
    default_actions_for_dimensions,
    default_actions_for_stage,
    resolve_action_target,
    resolve_workflow_entry,
)
from archium.application.context.presentation_cognition_gate import (
    PresentationCognitionGateResult,
    enforce_presentation_cognition_gate,
    evaluate_presentation_cognition,
)
from archium.application.context.presentation_readiness import (
    PresentationContextReadiness,
    PresentationGateVerdict,
    format_readiness_for_prompt,
    presentation_readiness_from_context,
)
from archium.application.context.project_context_builder import (
    build_project_context,
    input_sources_from_evidence,
    overlay_persisted_routing,
)
from archium.application.context.project_context_composer import (
    compose_project_context,
    finalize_assessment_context,
)
from archium.application.context.types import (
    ActionDispatch,
    ContextAssessment,
    WorkflowEntryDispatch,
)
from archium.application.context.workflow_navigation import (
    apply_workflow_entry,
    sync_mission_step_from_context,
    workflow_entry_for_project,
)

__all__ = [
    "ActionDispatch",
    "ContextAnalyzer",
    "ContextAssessment",
    "KnowledgeAssessor",
    "NbaActionExecutor",
    "NbaExecutionResult",
    "PresentationCognitionGateResult",
    "PresentationContextReadiness",
    "PresentationGateVerdict",
    "ReassessMode",
    "WorkflowEntryDispatch",
    "actions_for_presentation_entry",
    "actions_from_knowledge_vector",
    "apply_workflow_entry",
    "best_effort_reassess_knowledge",
    "build_project_context",
    "classify_reassess_mode",
    "compose_project_context",
    "default_actions_for_dimensions",
    "default_actions_for_stage",
    "enforce_presentation_cognition_gate",
    "evaluate_presentation_cognition",
    "finalize_assessment_context",
    "format_readiness_for_prompt",
    "input_sources_from_evidence",
    "merge_claim_index_into_state",
    "nba_execute_label",
    "overlay_persisted_routing",
    "presentation_readiness_from_context",
    "refresh_claim_index_only",
    "resolve_action_target",
    "resolve_workflow_entry",
    "sync_mission_step_from_context",
    "workflow_entry_for_project",
]
