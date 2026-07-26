# 03 — Application

模块：应用服务层  
前缀：`APP-`  
更新：2026-07-26（含第二轮设计循环 Issue）

相关：[第二轮-03 推理链](../life-system/03-ai-reasoning-chain.md) · [第二轮-04 设计循环](../life-system/04-design-loop.md)

| 编号 | 严重级别 | 状态 | 问题 | 文件 | 影响 | 修复方案 | 验收标准 | 提交 SHA |
|------|----------|------|------|------|------|----------|----------|----------|
| APP-001 | P0 | done | Application 泄漏 UI 依赖 (A1) | `layout_readiness.py`; layering 测试 | 无法无头复用 | 去掉 UI import；守卫 | `test_application_layering` 绿 | `-` |
| APP-002 | P0 | done | 双 PPTX 导出路径 Spec vs Scene (A2) | `FormalPptxExportService`；workflow/export 解耦 | 同项目两种结果 | 正式可编辑 PPTX 优先 Scene；Spec 仅 JSON/回退 | 有版式走 Scene；无版式 Spec 回退+警告 | `-` |
| APP-003 | P0 | done | `session.commit` 所有权不一致 (A3) | `session.py` 策略；TE；UI/嵌套 helper | 事务边界错乱 | UI 禁止 commit；嵌套 helper 只 flush；用例边界 allowlist + `test_commit_ownership` | TE 失败无 commit；UI/infra 无 commit；抽查边界绿 | `-` |
| APP-004 | P1 | open | QA 多栈并存 (A4) | AutomatedReview / DeckQA / SceneSemantic / Critic | 重复告警、门禁不清 | 编排层统一，其余只产证据 | 导出只读统一 verdict | `-` |
| APP-005 | P1 | open | 修复三路径并存 (A5) | SlideSpec / LayoutPlan / Scene repair | 修一处烂两处 | Scene 为修入口；其余适配 | repair 后 Scene+Plan 一致 | `-` |
| APP-006 | P1 | open | God services（千行级）(A6) | StudioCommandExecutor; VisualEditService 等 | 难测难审 | 按用例拆服务 | 单文件 < 约定上限 + 单测边界清晰 | `-` |
| APP-007 | P2 | open | `*_safe` 会话与死代码 IconSelection (A7) | application | 噪音 | 删除或正式化 | 无未引用符号 | `-` |
| APP-008 | P1 | done | DesignRationaleDraft 缺 observation/problem/hypothesis/strategy，与 Domain 断裂 | `concept_direction_schemas.py`; `concept_direction_mapping.py` | LLM 无法沉淀推理链；靠 fallback 合成答案 | Draft 对齐 Domain 链字段；映射写入 | 生成方向 rationale 含链字段；单测覆盖 | `-` |
| APP-009 | P1 | done | 建筑推理框架映射到分散方向字段，未写入 Rationale 链 | `prompts/frameworks/architectural_reasoning.py`; `prompts/concept_direction.py` | 产品叙事与数据模型错位 | Step→Rationale 字段映射；方向字段作表达层 | prompt 明示链字段；抽检输出可追溯 Step | `-` |
| APP-010 | P1 | done | DesignCritique / Reflection 无 Revise：next_adjustments 不执行 | `design_revise_service.py`; concept select | Critic 只挡不改 → AI 自嗨风险 | `revise_direction_from_critique`；可应用 adjustments | 批判后方向字段可更新；IntentEvolution 有边 | `-` |
| APP-011 | P2 | done | 无 ReasoningArtifact 身份；证据 refs 未绑定单一推理节点 | `reasoning_artifact.py`; concept/mission | 推理不可版本化/追溯 | 薄封装 id+project+evidence refs（复用 Rationale） | 推理节点可按 id 取；Critic 读同一节点 | `-` |
| APP-012 | P1 | open | Revise 后无再 Critique；设计循环未闭合 | `design_revise_service.py`; `*_maybe_revise_from_critique` | 修订可「看起来更好」却未再验证 | revise 后 rule/LLM 再批判；reject 仍走 warn/block | 修订后有第二份报告；单测覆盖 | `-` |
| APP-013 | P1 | open | 选定路径自动修订无人工确认 | `design_revise_service.py`; exploration/mission select | 相对 Critic 只读契约的静默改方向 | `DESIGN_REVISE_ON_SELECT=off\|auto\|ask`；ask 出示 diff | 默认策略文档化；ask 模式可拒补丁 | `-` |
| APP-014 | P2 | open | Reflection next_adjustments UI 无 Apply/Reject | `design_reflection_details.py`; `apply_reflection_adjustments` | 调整项只展示不执行 | UI 一键应用/拒绝 + IntentEvolution | Apply 后方向字段变；Reject 记边 | `-` |
| APP-015 | P2 | open | Mission select 不写 DESIGN_CRITIQUE IntentEvolution 边 | `concept_direction_service.select_direction` | 探索/Mission 历史不对称 | 与 exploration 对齐写 DESIGN_CRITIQUE | Mission 选定 caution/reject 有边 | `-` |
| APP-016 | P2 | open | Research Critic block 不拒绝落库/不挡概念硬化 | `research_critique_service.py`; autonomous research | 「block」名不副实 | block 拒写或拒绝进入 Design Critic 摘要 | block 下弱研究不可硬化 | `-` |
