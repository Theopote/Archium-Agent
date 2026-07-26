# 第二轮-08：商业化与团队协作审计

**日期：** 2026-07-26  
**范围：** ProjectMember / Invite / RBAC / ProjectEvent / LLMTrace / 身份 / 用量 / tenancy  
**核心问题：** 产品闭环（Topic 07）可走通后，能否支撑**真实团队**（建筑师 / 审阅者 / 甲方）协作、分权、计量——且不新增 Agent？

**前置：** Topic 07 L1–L3；Phase N 已落地成员/邀请/事件/Trace 表。本专题查**产品商业化胶合**，不重复世界模型字段审计。

---

## 一句话结论

**协作与记忆底座已建；产品仍按单用户 Streamlit 运行。** 权限模型在、写路径未接线；无可信身份、无组织/计费层。`LLMTrace` 可作用量原料，尚非账单。

---

## 理想 vs 现状

```text
理想：
  Auth → Org → Project membership + roles
       ↓
  角色化 UI（Architect / Reviewer / Client）
       ↓
  共享设计记忆（IntentEvolution + ProjectEvent + 归因）
       ↓
  用量聚合 → 席位/配额 → 计费

现状：
  [Phase N 底座]                 [产品单用户壳]
  project_members + invites      无 login；LOCAL_ACTOR_ID 硬编码
  ProjectAccessService（逻辑）    写路径几乎未 enforce
  ProjectEvent + LLMTrace        无 member 归因 / 无用量 UI
  IntentEvolution 持久（L2）      设计页可见；无角色分视图
  ElementComment Inbox           无 RBAC / 指派
  Home 成员面板                  孤岛；非主 chrome
```

| 层 | 成熟度 | 落点 |
|----|--------|------|
| Domain RBAC | B- | `access.py` 四角色 |
| 权限接线 | **D→C（C1）** | 成员过滤 + session actor；写路径仍欠 |
| 邀请 | B- | 码+TTL；无 deep link / 邮件 |
| 共享记忆 | B | ProjectEvent / IntentEvolution |
| LLMTrace | B- | 可持久；无聚合 UI |
| Studio 评论 | C+ | ElementComment；无协作者身份 |
| Auth / Org | F | 无 SSO；无 Organization |
| 计费 | F | 无 seat/quota/Stripe |

---

## 亮点（勿推倒）

1. 四角色贴合事务所（Owner / Architect / Reviewer / Client）  
2. ProjectEvent 投影 IntentEvolution — 共享记忆正确抽象  
3. LLMTrace 禁 prompt/密钥 — 可直接做 usage rollup  
4. ElementComment + HumanGate 是异步协作正确起点  
5. 不需新 Agent：Service + Domain + UI chrome 即可

---

## 裂缝取证（摘要）

1. **`ProjectAccessService.require` 几乎只服务成员/邀请** — Mission/Studio/Generate/Ingest 未挡  
2. **`list_projects` → `list_all()`** — 实例内项目全可见  
3. **Bootstrap：** 无成员时 `local-user` 获全权限（遗留项目）  
4. **Redeem 自填 actor_id** — 身份可伪造  
5. **无 Organization** — 多客户事务所 SaaS 无根对象  
6. **用量：** Trace 有、账单无  

---

## 建议演进

### Phase C1 — 身份与可见项目（P0–P1）✅ 2026-07-26

1. Session `actor_id` SSOT（默认 `local-user`；可切换）  
2. `list_visible_projects(actor)` — 有成员记录则过滤；本地单用户无记录时兼容 `list_all`  
3. 无成员项目：首次 `local-user` 访问 `ensure_default_owner`（关闭无限 bootstrap）  
4. 薄门面 `require_project_permission`（供后续写路径接入）

（关闭 `COLLAB-002` / `COLLAB-003` / `SEC-001` 部分；`COLLAB-001` 写路径仍开。）

### Phase C2 — 角色化协作（P1–P2）

5. Invite deep link `?invite=`  
6. Client/Reviewer 角色化 chrome  
7. ElementComment.`created_by` = actor_id；ProjectEvent 可选 actor 归因  
8. HumanGate + actor 顶栏（接 UI-009 / UI-010）

### Phase C3 — 用量 / tenancy 骨架（P2）

9. Token rollup by project/month  
10. Soft quota warn  
11. 可选 `Organization` 占位（DOM-032）

**不做：** 新 Agent；完整 IdP；生产 Stripe；实时 CRDT 协同；多 region。

---

## 可行动 Issue

| 编号 | 级别 | 问题 |
|------|------|------|
| COLLAB-001 | P0 | RBAC 未接写路径（Mission/Studio/Generate…） |
| COLLAB-002 | P1 | ~~list_all 无成员过滤~~ **done (C1)** |
| COLLAB-003 | P1 | ~~无 session actor SSOT~~ **done (C1)** |
| COLLAB-004 | P1 | 邀请仅 Home 手输；无 deep link |
| COLLAB-005 | P1 | 无 Client/Reviewer 角色化导航 |
| COLLAB-006 | P2 | ProjectEvent 无 member 级 attribution |
| SEC-001 | P0 | ~~无成员时 local-user 全权限 bootstrap~~ **mitigated (C1)** |
| SEC-002 | P1 | 无 OAuth；actor_id 可伪造 |
| APP-028 | P1 | ~~缺统一 require 门面~~ **done (C1 门面)**；写路径接线仍属 COLLAB-001 |
| UI-010 | P1 | 无全局 actor/role 顶栏 |
| BILL-001 | P2 | 无 token 聚合 / 项目用量 UI |
| BILL-002 | P2 | 无 seat / quota 模型 |
| DOM-032 | P2 | 无 Organization / tenant 根对象 |

---

## 专题衔接

| 专题 | 钩子 |
|------|------|
| 07 产品闭环 | 可续闭环是协作前提；continue_work 尚不知角色 |
| 01 Domain | 无 Org 根（DOM-032） |
| 04 设计循环 | Ask durable；缺「谁 Apply」归因 |
| module-audit | `15-collaboration` / `16-billing-usage` |

---

## 验收

- [x] 路径取证与理想对照  
- [x] Issue 登记 module-audit  
- [x] Phase C1 身份与可见项目  
- [ ] Phase C2 角色化协作  
- [ ] Phase C3 用量 / tenancy
