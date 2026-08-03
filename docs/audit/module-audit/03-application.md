# 03 — Application

模块：应用服务层  
前缀：`APP-`  
更新：2026-07-26（含第二轮设计循环 Issue）

相关：[第二轮-03 推理链](../life-system/03-ai-reasoning-chain.md) · [第二轮-04 设计循环](../life-system/04-design-loop.md) · [第二轮-07 产品闭环](../life-system/07-product-loop.md)

| 编号 | 严重级别 | 状态 | 问题 | 文件 | 影响 | 修复方案 | 验收标准 | 提交 SHA |
|------|----------|------|------|------|------|----------|----------|----------|
| APP-001 | P0 | done | Application 泄漏 UI 依赖 (A1) | `layout_readiness.py`; layering 测试 | 无法无头复用 | 去掉 UI import；守卫 | `test_application_layering` 绿 | `-` |
| APP-002 | P0 | done | 双 PPTX 导出路径 Spec vs Scene (A2) | `FormalPptxExportService`；workflow/export 解耦 | 同项目两种结果 | 正式可编辑 PPTX 优先 Scene；Spec 仅 JSON/回退 | 有版式走 Scene；无版式 Spec 回退+警告 | `-` |
| APP-003 | P0 | done | `session.commit` 所有权不一致 (A3) | `session.py` 策略；TE；UI/嵌套 helper | 事务边界错乱 | UI 禁止 commit；嵌套 helper 只 flush；用例边界 allowlist + `test_commit_ownership` | TE 失败无 commit；UI/infra 无 commit；抽查边界绿 | `-` |
| APP-004 | P1 | done | QA 多栈并存 (A4) | AutomatedReview / DeckQA / SceneSemantic / Critic | 重复告警、门禁不清 | 编排层统一，其余只产证据 | 导出只读统一 verdict | Topic 07 APP-004 |
| APP-005 | P1 | done | 修复三路径并存 (A5) | SlideSpec / LayoutPlan / Scene repair | 修一处烂两处 | Scene 为修入口；其余适配 | repair 后 Scene+Plan 一致 | Topic 07 APP-005 |
| APP-006 | P1 | open | God services（千行级）(A6) | StudioCommandExecutor; VisualEditService 等 | 难测难审 | 按用例拆服务 | 单文件 < 约定上限 + 单测边界清晰 | `-` |
| APP-007 | P2 | open | `*_safe` 会话与死代码 IconSelection (A7) | application | 噪音 | 删除或正式化 | 无未引用符号 | `-` |
| APP-008 | P1 | done | DesignRationaleDraft 缺 observation/problem/hypothesis/strategy，与 Domain 断裂 | `concept_direction_schemas.py`; `concept_direction_mapping.py` | LLM 无法沉淀推理链；靠 fallback 合成答案 | Draft 对齐 Domain 链字段；映射写入 | 生成方向 rationale 含链字段；单测覆盖 | `-` |
| APP-009 | P1 | done | 建筑推理框架映射到分散方向字段，未写入 Rationale 链 | `prompts/frameworks/architectural_reasoning.py`; `prompts/concept_direction.py` | 产品叙事与数据模型错位 | Step→Rationale 字段映射；方向字段作表达层 | prompt 明示链字段；抽检输出可追溯 Step | `-` |
| APP-010 | P1 | done | DesignCritique / Reflection 无 Revise：next_adjustments 不执行 | `design_revise_service.py`; concept select | Critic 只挡不改 → AI 自嗨风险 | `revise_direction_from_critique`；可应用 adjustments | 批判后方向字段可更新；IntentEvolution 有边 | `-` |
| APP-011 | P2 | done | 无 ReasoningArtifact 身份；证据 refs 未绑定单一推理节点 | `reasoning_artifact.py`; concept/mission | 推理不可版本化/追溯 | 薄封装 id+project+evidence refs（复用 Rationale） | 推理节点可按 id 取；Critic 读同一节点 | `-` |
| APP-012 | P1 | done | Revise 后无再 Critique；设计循环未闭合 | `design_loop.py`; `*_maybe_revise_from_critique` | 修订可「看起来更好」却未再验证 | revise 后 rule/LLM 再批判；reject 仍走 warn/block | 修订后有第二份报告；单测覆盖 | `-` |
| APP-013 | P1 | done | 选定路径自动修订无人工确认 | `design_loop.py`; `design_revise_ask_panel.py` | 相对 Critic 只读契约的静默改方向 | `DESIGN_REVISE_ON_SELECT=off\|auto\|ask`；ask 出示 diff | 默认 ask；Apply/Reject 可选定 | `-` |
| APP-014 | P2 | done | Reflection next_adjustments UI 无 Apply/Reject | `design_revise_ask_panel.py`; reflection 预览 | 调整项只展示不执行 | Ask 面板展示 adjustments + Apply/Reject | Apply 后方向字段变；Reject 记边 | `-` |
| APP-015 | P2 | done | Mission select 不写 DESIGN_CRITIQUE IntentEvolution 边 | `concept_direction_service.select_direction` | 探索/Mission 历史不对称 | 与 exploration 对齐写 DESIGN_CRITIQUE | Mission 选定有 DESIGN_CRITIQUE 边 | `-` |
| APP-016 | P2 | done | Research Critic block 不拒绝落库/不挡概念硬化 | `autonomous_research_service._attach_research_critique` | 「block」名不副实 | WEAK+block → reject items + WorkflowError | block 下弱研究不可硬化 | `-` |
| APP-017 | P1 | done | 多模态检索默认 ILLUSTRATIVE；项目素材未进 EVIDENCE | `multimodal_retrieval.py`; life-system 05 | 设计通道看不到现场证据 | PROJECT_MATERIAL photo/drawing → EVIDENCE | 检索 usage=evidence；生成图仍 illustrative | `-` |
| APP-018 | P1 | done | ProjectContext.input_sources 无类型化视觉证据摘要 | `context_evidence.py`; composer | 认知面看不见 site_photo/drawing | gather + compose 写入 site_photo:N 等 | Context.input_sources 含视觉行 | `-` |
| APP-019 | P2 | done | 草图/现场图未种子化 IdeaSeed/Direction | `visual_idea_seed.py`; upload hook | 多模态停在 RAG | 弱种子 enrich=False；不自动推演/选定 | 上传现场图可开探索；无 SELECTED | `-` |
| APP-020 | P2 | done | UI 上传未暴露 CAD/BIM 类型 | `upload_file_types.py`; workspace/studio | CAD 只能旁路 | file_uploader 加 dwg/dxf/ifc/rvt/rfa | UI 可选 CAD/BIM | `-` |
| APP-021 | P2 | done | IFC/CAD 文本语义未写入 ProjectFact | `cad_spatial_fact_materializer.py`; ifc_text_semantics | 空间计数停在 chunk 散文 | floors/constraints/main_function 白名单落账 | IFC 导入有 floors；可测 | `-` |
| APP-022 | P2 | done | DOCUMENT_ANALYZE 完成不回写文档/事实 | `background_job_worker.py` | 异步分析对世界模型无效 | 合并 metadata + materialize facts | job 后 doc 有 parse_depth；有事实 | `-` |
| APP-023 | P2 | done | 视觉证据包缺 CAD/BIM 文档门面 | `visual_evidence_service`; architectural_asset_from_document | Context 不见 cad_bim:N | 文档级 facade 入 pack | input_sources 含 cad_bim | `-` |
| APP-024 | P1 | done | Direction/Brief→ImageRequest 缺 seed_source | `vision_generation.ImageRequest`; concept/brief/suggester seeds | 页意图来源不可追溯 | seed_source 字段 + 方向优先 | 方向种子可测；示意策略不变 | `-` |
| APP-025 | P2 | done | 册级 illustrative hero 风格无共享锁 | `deck_illustrative_style_lock.py`; visual_intent; VT slots | 跨页插图漂移 | 方向 style 锁 + 非证据页统一；槽位保 image_type | 非证据页共享 style；诊断页不锁 | `-` |
| APP-026 | P1 | done | pending_design_revise / critique UI 仅 session；闭环不可恢复 | `intent_evolution.py`; `design_revise_persistence.py`; ask panel | 刷新丢失 Ask；Deliver 不见批判 | 落 IntentEvolution.pending + Hydrate | 刷新后 Ask 可恢复；Deliver/Outline 可读最近批判 | Topic 07 L2 |
| APP-027 | P2 | done | 设计批判未 Hydrate 到 Deliver/Outline；不驱动 NBA | `critique_summary_panel`; IntentEvolution DESIGN_CRITIQUE | 批判结论无下游行动 | 读边/pending → 回探索 page_link | Outline/Deliver 有可点行动 | Topic 07 L2 |
| APP-028 | P1 | done | 缺统一 `require_project_permission` 门面 | `project_permission_gate.py` | 写路径各自绕过 | 薄门面；COLLAB-001 接线仍开 | 门面单测绿 | Topic 08 C1 |
| APP-029 | P2 | done | 无稳定 Application API；UI 直连 Repository；Job 缺取消/幂等 | `application/api/*`; BackgroundJob | 难换客户端、刷新丢任务 | 进程内 API（含 `/visual`）+ Jobs；pages 禁 Repository；Studio/Visual/Planning 高频读走 API；ingest enqueue analyze | `test_application_api` + pages layering 绿 | `-` |
