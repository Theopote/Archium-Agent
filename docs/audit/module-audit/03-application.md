# 03 — Application

模块：应用服务层  
前缀：`APP-`  
更新：2026-07-23

| 编号 | 严重级别 | 状态 | 问题 | 文件 | 影响 | 修复方案 | 验收标准 | 提交 SHA |
|------|----------|------|------|------|------|----------|----------|----------|
| APP-001 | P0 | done | Application 泄漏 UI 依赖 (A1) | `layout_readiness.py`; layering 测试 | 无法无头复用 | 去掉 UI import；守卫 | `test_application_layering` 绿 | `-` |
| APP-002 | P0 | done | 双 PPTX 导出路径 Spec vs Scene (A2) | `FormalPptxExportService`；workflow/export 解耦 | 同项目两种结果 | 正式可编辑 PPTX 优先 Scene；Spec 仅 JSON/回退 | 有版式走 Scene；无版式 Spec 回退+警告 | `-` |
| APP-003 | P0 | done | `session.commit` 所有权不一致 (A3) | `session.py` 策略；TE；UI/嵌套 helper | 事务边界错乱 | UI 禁止 commit；嵌套 helper 只 flush；用例边界 allowlist + `test_commit_ownership` | TE 失败无 commit；UI/infra 无 commit；抽查边界绿 | `-` |
| APP-004 | P1 | open | QA 多栈并存 (A4) | AutomatedReview / DeckQA / SceneSemantic / Critic | 重复告警、门禁不清 | 编排层统一，其余只产证据 | 导出只读统一 verdict | `-` |
| APP-005 | P1 | open | 修复三路径并存 (A5) | SlideSpec / LayoutPlan / Scene repair | 修一处烂两处 | Scene 为修入口；其余适配 | repair 后 Scene+Plan 一致 | `-` |
| APP-006 | P1 | open | God services（千行级）(A6) | StudioCommandExecutor; VisualEditService 等 | 难测难审 | 按用例拆服务 | 单文件 < 约定上限 + 单测边界清晰 | `-` |
| APP-007 | P2 | open | `*_safe` 会话与死代码 IconSelection (A7) | application | 噪音 | 删除或正式化 | 无未引用符号 | `-` |
