# Application Service Layer Refactoring Plan

## Current State
The `archium/application/` directory contains 140+ service files, making it difficult to navigate and maintain. Some subdirectories exist (narrative, visual, context, review) but many services remain in the root directory.

## Proposed Structure

### New Directory Structure
```
archium/application/
├── __init__.py
├── _helpers.py
├── narrative/              # Existing - Narrative/storyline services
├── visual/                 # Existing - Visual design and layout services  
├── context/                # Existing - Context and intelligence services
├── review/                 # Existing - Review and QA services
├── mission/                # NEW - Mission planning and clarification
│   ├── __init__.py
│   ├── mission_clarification_service.py
│   ├── mission_history_service.py
│   ├── mission_research_enrichment_service.py
│   ├── mission_validation_service.py
│   ├── mission_to_presentation_request.py
│   ├── deliverable_planning_service.py
│   └── workstream_planning_service.py
├── project/                # NEW - Project management and access
│   ├── __init__.py
│   ├── project_management_service.py
│   ├── project_access_service.py
│   ├── project_mission_service.py
│   ├── project_knowledge_service.py
│   ├── project_event_service.py
│   ├── project_invite_service.py
│   ├── project_deletion_service.py
│   └── organization_service.py
├── asset/                  # NEW - Asset management and matching
│   ├── __init__.py
│   ├── asset_board_service.py
│   ├── asset_matching_service.py
│   ├── asset_metadata_service.py
│   ├── asset_presentation_readiness_service.py
│   ├── asset_vision_rag_service.py
│   └── evidence_item_binding_service.py
├── knowledge/              # NEW - Knowledge and fact management
│   ├── __init__.py
│   ├── fact_extraction_service.py
│   ├── fact_ledger_service.py
│   ├── fact_validation_service.py
│   ├── knowledge_graph_service.py
│   ├── knowledge_fusion.py
│   ├── knowledge_vector_index.py
│   └── retrieval_service.py
├── presentation/           # NEW - Presentation generation and workflow
│   ├── __init__.py
│   ├── presentation_service.py
│   ├── presentation_workflow_service.py
│   ├── presentation_manuscript_service.py
│   ├── presentation_intent_layer.py
│   ├── presentation_critic.py
│   ├── outline_service.py
│   ├── slide_design_brief_service.py
│   ├── slide_generation_context_service.py
│   └── regeneration_service.py
├── slide/                  # NEW - Slide-specific operations
│   ├── __init__.py
│   ├── slide_recovery_service.py
│   ├── slide_repair_service.py
│   ├── slide_semantic_qa_service.py
│   ├── slide_split_planner.py
│   ├── slide_history_service.py
│   ├── slide_asset_binding_service.py
│   └── slide_evidence_edit_service.py
├── design/                 # NEW - Design and concept services
│   ├── __init__.py
│   ├── concept_direction_service.py
│   ├── design_revise_service.py
│   ├── design_artifact_catalog.py
│   ├── design_knowledge_mapping.py
│   └── spatial_design_layer.py
├── export/                 # NEW - Export and rendering services
│   ├── __init__.py
│   ├── export_service.py
│   ├── export_policy_service.py
│   ├── export_round_trip_service.py
│   ├── formal_pptx_export_service.py
│   └── render_export.py
├── ingestion/              # NEW - Document ingestion and parsing
│   ├── __init__.py
│   ├── ingestion_service.py
│   ├── chunk_service.py
│   └── multimodal_retrieval.py
├── research/               # NEW - Research and analysis services
│   ├── __init__.py
│   ├── autonomous_research_service.py
│   ├── research_question_service.py
│   ├── research_topics.py
│   └── retrieval_credibility.py
├── artifact/               # NEW - Artifact and job management
│   ├── __init__.py
│   ├── artifact_history_service.py
│   ├── artifact_job_service.py
│   ├── artifact_policy_service.py
│   ├── artifact_snapshots.py
│   └── artifact_lineage.py
├── workflow/               # NEW - Workflow orchestration
│   ├── __init__.py
│   ├── planning_workflow_service.py
│   ├── workflow_route_service.py
│   ├── workflow_progress.py
│   └── workflow_checkpoint.py
├── llm/                    # NEW - LLM-related services
│   ├── __init__.py
│   ├── llm_profile_service.py
│   ├── llm_settings_resolver.py
│   └── model_role_router.py
├── ui/                     # NEW - UI-specific services
│   ├── __init__.py
│   ├── workspace_mode_service.py
│   ├── product_continue_work.py
│   └── product_stage_truth.py
└── orchestration/          # NEW - Orchestration services
    ├── __init__.py
    ├── workflow_orchestration_service.py
    └── workstream_execution_service.py
```

## Migration Strategy

### Phase 1: Create New Directories
1. Create new subdirectories with `__init__.py` files
2. Set up lazy import patterns in each `__init__.py`

### Phase 2: Move Service Files
1. Move files according to the grouping above
2. Update imports throughout the codebase
3. Update the main `archium/application/__init__.py`

### Phase 3: Update Tests
1. Update test imports
2. Verify all tests pass

### Phase 4: Documentation
1. Update README and architecture docs
2. Add service layer documentation

## Benefits
- **Better organization**: Services grouped by business domain
- **Easier navigation**: Clearer structure for developers
- **Reduced cognitive load**: Smaller, focused directories
- **Better maintainability**: Easier to locate and modify services
- **Scalability**: Clear pattern for adding new services

## Backward Compatibility
- Maintain lazy imports in `__init__.py` files
- Keep existing import paths working through re-exports
- Provide deprecation warnings for old import paths if needed
