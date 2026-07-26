# 16 — Billing / usage / tenancy

模块：用量计量、席位配额、组织 tenancy  
前缀：`BILL-`  
更新：2026-07-26（Topic 08）

相关：[第二轮-08 商业化与协作](../life-system/08-commercialization-collab.md) · 安全侧见 [14-tests-security.md](14-tests-security.md) `SEC-*` 若新增

| 编号 | 严重级别 | 状态 | 问题 | 文件 | 影响 | 修复方案 | 验收标准 | 提交 SHA |
|------|----------|------|------|------|------|----------|----------|----------|
| BILL-001 | P2 | done | 无 token 聚合 / 项目用量 UI | `usage_rollup_service`; Home strip | 无法定价/控本 | sum by project/month | Home 可看用量 | Topic 08 C3 |
| BILL-002 | P2 | mitigated | 无 seat / quota 模型 | `llm_usage_soft_budget_tokens` | 无法限席位 | soft budget warn（非硬阻断） | 超配额 Home 警告；席位模型仍欠 | Topic 08 C3 |
| BILL-003 | P3 | open | 无 Stripe/subscription 集成 | — | 无法收款 | 延后至产品门禁后 | — | `-` |
| DOM-032 | P2 | done | 无 Organization / tenant 根对象 | `organization.py`; `060_organizations` | 多客户事务所分裂 | 薄 Org + nullable FK | 单测可挂 org | Topic 08 C3 |
