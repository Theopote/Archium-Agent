# 02 — Domain

模块：领域模型与分层边界  
前缀：`DOM-`  
更新：2026-07-23

| 编号 | 严重级别 | 状态 | 问题 | 文件 | 影响 | 修复方案 | 验收标准 | 提交 SHA |
|------|----------|------|------|------|------|----------|----------|----------|
| DOM-001 | P0 | done | Domain 内含解析器实现（分层违规） | `archium/domain/`; `archium/application/visual/` | Domain 依赖 IO/解析 | 解析迁出 application；守卫 | `pytest` domain layering 相关单测绿 | `-` |
| DOM-002 | P0 | done | `scene_semantic_qa` 分叉残留 | domain visual QA | 双份语义 QA | 删除分叉，统一入口 | 无残留模块；引用更新 | `-` |
| DOM-003 | P1 | open | `PresentationSpec` 与 `RenderScene` 并存作导出真相 (D3) | `archium/domain/` presentation / visual | 双 SSOT，导出不一致 | 明确 Scene 为渲染 SSOT；Spec 降级或生成派生 | 单一导出路径文档 + 合同测试 | `-` |
| DOM-004 | P1 | open | Severity 词汇表 ≥4 套 (D4) | Review / Validation / LayoutIssue / Issue | 门禁语义混乱 | 统一 catalog + 映射层 | 导出门禁只认一套枚举 | `-` |
| DOM-005 | P1 | open | 页类型枚举重叠 (D5) | `SlideType` / `FunctionalSlideType` 等 | 规划/渲染错配 | 收敛或显式映射表 | 无隐式字符串互转 | `-` |
| DOM-006 | P1 | open | `SlideDesignBrief.layout_family` 为自由字符串 (D6) | design brief 模型 | 布局族无法校验 | 枚举或受控词表 | 非法 family 被拒绝 | `-` |
| DOM-007 | P1 | open | `WorkflowStep` 过大耦合 (D7) | domain workflow enums | 难演进 | 拆分阶段枚举 | 图定义不依赖巨枚举细节 | `-` |
| DOM-008 | P1 | open | Fact 三模型弱关联 (D8) | ProjectFact / Knowledge / Manuscript | 引用断裂 | 显式 ID 链接 + 不变量 | 跨模型引用可追溯 | `-` |
| DOM-009 | P2 | open | ProposalStatus 等克隆枚举 (D9) | domain | 漂移 | 合并 | 单一状态机 | `-` |
| DOM-010 | P2 | open | Chart/Table series 深拷贝行为不清 (D10) | domain visual | 静默丢数据 | 明确 copy 语义 + 测试 | 变更系列不丢字段 | `-` |
