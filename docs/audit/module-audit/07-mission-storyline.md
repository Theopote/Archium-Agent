# 07 — Mission / storyline

模块：Mission、Workstream、Storyline、DeliverablePlan  
前缀：`MS-`  
更新：2026-07-23

| 编号 | 严重级别 | 状态 | 问题 | 文件 | 影响 | 修复方案 | 验收标准 | 提交 SHA |
|------|----------|------|------|------|------|----------|----------|----------|
| MS-001 | P0 | done | Workstream 重选未使计划失效；陈旧 draft；narrative 旁路 | mission / planning services | 用错计划继续生成 | 失效 + draft 守卫；narrative 走 PlanningSession | 重选后须重批；无旁路 | `-` |
| MS-002 | P1 | open | Presentation/Request 无持久 `mission_id` (M1) | domain / ORM | 汇报与任务脱钩 | 外键或强引用字段 | 导出/Studio 可溯源 mission | `-` |
| MS-003 | P1 | open | `narrative_mode` 双轨 (M2) | planning | 模式不一致 | 单一来源 | 读写同字段 | `-` |
| MS-004 | P1 | open | Outline 合同松散 (M3) | storyline | 页序漂移 | 结构化合同 + 测试 | golden/mission 覆盖合同 | `-` |
| MS-005 | P1 | open | Plan 缺稳定内容哈希 (M4)（同 WF-006） | DeliverablePlan | 批后篡改 | content hash | 见 WF-006 | `-` |
| MS-006 | P2 | open | 未用 mode / WorkstreamPlan / OutlineApprovalRecord 残留 (M5–M7) | domain | 死模型 | 接线或删除 | 无未引用模型 | `-` |
