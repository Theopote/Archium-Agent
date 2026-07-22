"""Catalog: technology-radar adopt concepts → main-chain bindings."""

from __future__ import annotations

from archium.domain.main_chain_adopt import MainChainAdoptBinding

MAIN_CHAIN_ADOPT_BINDINGS: tuple[MainChainAdoptBinding, ...] = (
    # PPTAgent
    MainChainAdoptBinding(
        concept_id="pptagent_multi_step_reflection",
        label_zh="多步骤推理与反思式生成",
        source_system_id="pptagent",
        main_chain_stage="generate",
        enforcement_module="presentation_workflow_service / deck_coherence_qa_service",
        gate_hint_zh="生成后应运行 deck 叙事 QA 或多步工作流",
    ),
    MainChainAdoptBinding(
        concept_id="pptagent_template_induction",
        label_zh="模板归纳而非硬编码版式",
        source_system_id="pptagent",
        main_chain_stage="outline",
        enforcement_module="template_induction_service / layout_family_registry",
        gate_hint_zh="优先使用模板归纳或 LayoutFamily 注册表",
    ),
    MainChainAdoptBinding(
        concept_id="pptagent_reference_structure",
        label_zh="参考页结构提取",
        source_system_id="pptagent",
        main_chain_stage="outline",
        enforcement_module="reference_pptx_parser",
        gate_hint_zh="绑定参考 PPT 或参考风格档案",
    ),
    # presentation-ai
    MainChainAdoptBinding(
        concept_id="presentation_ai_tool_calls",
        label_zh="AI 工具调用驱动编辑",
        source_system_id="presentation-ai",
        main_chain_stage="edit",
        enforcement_module="studio_command / visual_edit_service",
        platform_builtin=True,
    ),
    MainChainAdoptBinding(
        concept_id="presentation_ai_before_after",
        label_zh="Before/After 提案与显式接受",
        source_system_id="presentation-ai",
        main_chain_stage="edit",
        enforcement_module="scene_proposal_service",
        platform_builtin=True,
    ),
    MainChainAdoptBinding(
        concept_id="presentation_ai_structured_ops",
        label_zh="结构化 slide 操作",
        source_system_id="presentation-ai",
        main_chain_stage="edit",
        enforcement_module="scene_change_proposal / studio_command",
        platform_builtin=True,
    ),
    # slide-deck-ai
    MainChainAdoptBinding(
        concept_id="slide_deck_stage_contract",
        label_zh="简洁阶段契约",
        source_system_id="slide-deck-ai",
        main_chain_stage="materials",
        enforcement_module="product_flow / evaluate_stage_gate",
        platform_builtin=True,
    ),
    MainChainAdoptBinding(
        concept_id="slide_deck_narrative_arc",
        label_zh="叙事弧线驱动页序",
        source_system_id="slide-deck-ai",
        main_chain_stage="outline",
        enforcement_module="narrative_arc / outline_planning",
        gate_hint_zh="Storyline 需填写 narrative_arc，章节标注 narrative_position",
    ),
    MainChainAdoptBinding(
        concept_id="slide_deck_fault_tolerant_export",
        label_zh="真实 PPTX 模板与容错导出",
        source_system_id="slide-deck-ai",
        main_chain_stage="deliver",
        enforcement_module="export_policy_service / export_round_trip_service",
        gate_hint_zh="导出应附带保真度 Manifest 与 Round-trip QA",
    ),
    # SlideBot-AI
    MainChainAdoptBinding(
        concept_id="slidebot_per_page_binding",
        label_zh="逐页素材绑定",
        source_system_id="slidebot-ai",
        main_chain_stage="generate",
        enforcement_module="slide_asset_binding / page_asset_bindings",
        gate_hint_zh="图文/图纸页应绑定 page_asset_bindings",
    ),
    MainChainAdoptBinding(
        concept_id="slidebot_per_page_retry",
        label_zh="逐页状态与单页重试",
        source_system_id="slidebot-ai",
        main_chain_stage="generate",
        enforcement_module="page_status_board_service / regeneration_service",
        platform_builtin=True,
    ),
    MainChainAdoptBinding(
        concept_id="slidebot_guided_workflow",
        label_zh="引导式工作流",
        source_system_id="slidebot-ai",
        main_chain_stage="generate",
        enforcement_module="flow/generate / page_status_board_panel",
        platform_builtin=True,
    ),
    # Slideweaver
    MainChainAdoptBinding(
        concept_id="slideweaver_native_layout",
        label_zh="程序化布局与原生对象",
        source_system_id="slideweaver",
        main_chain_stage="generate",
        enforcement_module="render_scene_compiler / layout_plan",
        gate_hint_zh="页面应编译为 RenderScene 原生节点",
    ),
    MainChainAdoptBinding(
        concept_id="slideweaver_render_qa",
        label_zh="导出后渲染 QA",
        source_system_id="slideweaver",
        main_chain_stage="deliver",
        enforcement_module="export_round_trip_service",
        gate_hint_zh="PPTX 导出后执行 Round-trip 校验",
    ),
    MainChainAdoptBinding(
        concept_id="slideweaver_file_integrity",
        label_zh="文件完整性验证",
        source_system_id="slideweaver",
        main_chain_stage="deliver",
        enforcement_module="export_policy_service / deck_export_manifest",
        gate_hint_zh="导出 Manifest 应记录保真度与阻塞项",
    ),
)
