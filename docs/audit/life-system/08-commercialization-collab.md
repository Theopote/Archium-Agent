# 第二轮-08：商业化与团队协作审计

**日期：** 2026-07-26  
**范围：** ProjectMember / Invite / RBAC / ProjectEvent / LLMTrace / 身份 / 用量 / tenancy  
**核心问题：** 产品闭环（Topic 07）可走通后，能否支撑**真实团队**（建筑师 / 审阅者 / 甲方）协作、分权、计量——且不新增 Agent？

**前置：** Topic 07 L1–L3；Phase N 已落地成员/邀请/事件/Trace 表。本专题查**产品商业化胶合**，不重复世界模型字段审计。

---

## 一句话结论

**协作底座 + C1–C3 产品胶合已落地一截；仍非完整商业化。** 可见项目、关键写路径、邀请 deep link、角色化 chrome、事件成员归因已通。无可信 IdP、无 Org/计费层；`LLMTrace` 可作用量原料，尚非账单。

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
  [Phase N + C1–C3]              [仍欠]
  session actor + visible list   无 login / OAuth（SEC-002）
  关键写路径 require               Studio 细粒度 / 评论 RBAC
  ?invite= deep link             邮件外发
  角色化 continue + chrome        全局顶栏 actor 切换仍薄
  ProjectEvent + member actor_id  Studio 评论归因 / 用量 UI / Org
```

| 层 | 成熟度 | 落点 |
|----|--------|------|
| Domain RBAC | B- | `access.py` 四角色 |
| 权限接线 | **B（C1–C2）** | 可见项目 + 关键写路径；Studio 细粒度仍欠 |
| 邀请 | **B（C2）** | 码+TTL + `?invite=` deep link |
| 角色化 UI | **B-（C3）** | continue + design strip + 编辑预警 |
| 共享记忆 | **B+（C3）** | ProjectEvent / IntentEvolution + member `actor_id` |
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

1. ~~写路径未 enforce~~ → **C2 已挡**关键 create/import/run/select/export（Studio 细粒度仍欠）  
2. ~~`list_all` 全可见~~ → **C1 `list_visible_projects`**  
3. ~~无成员无限 bootstrap~~ → **C1 `ensure_default_owner` 收窄**  
4. **Redeem 自填 actor_id** — 身份可伪造（SEC-002）  
5. **无 Organization** — 多客户事务所 SaaS 无根对象（DOM-032）  
6. **用量：** Trace 有、账单无（BILL-001/002）  
7. ~~事件归因~~ → **C3 payload `actor_id`**（选定/批准/创建/兑换）；Studio 评论归因仍欠  

---

## 建议演进

### Phase C1 — 身份与可见项目（P0–P1）✅ 2026-07-26

1. Session `actor_id` SSOT（默认 `local-user`；可切换）  
2. `list_visible_projects(actor)` — 有成员记录则过滤；本地单用户无记录时兼容 `list_all`  
3. 无成员项目：首次 `local-user` 访问 `ensure_default_owner`（关闭无限 bootstrap）  
4. 薄门面 `require_project_permission`（供后续写路径接入）

（关闭 `COLLAB-002` / `COLLAB-003` / `SEC-001` 部分；写路径属 C2。）

### Phase C2 — 写路径 + 邀请链（P0–P1）✅ 2026-07-26

5. **写路径 RBAC：** create presentation / prepare_run / import / select direction / formal export  
6. **Invite deep link：** `?invite=CODE` → Home pending → 成员面板预填兑换  
7. UI select/import 传 `get_current_actor_id()`  

（关闭 `COLLAB-001` / `COLLAB-004`。）

### Phase C3 — 角色化 UI ✅ 切片（2026-07-26）；用量仍开

8. **Client/Reviewer 角色化 chrome（COLLAB-005）** — `role_navigation` + continue_work + design strip + 编辑预警  
9. **ProjectEvent member attribution（COLLAB-006）** — payload `actor_id`；选定/批准/创建/邀请兑换  
10. Token rollup + soft quota（BILL-001/002）— **仍开**  
11. 可选 Organization（DOM-032）— **仍开**

**不做：** 新 Agent；完整 IdP；生产 Stripe；实时 CRDT 协同；多 region。

---

## 可行动 Issue

| 编号 | 级别 | 问题 |
|------|------|------|
| COLLAB-001 | P0 | ~~写路径未接线~~ **done (C2)** |
| COLLAB-002 | P1 | ~~list_all 无成员过滤~~ **done (C1)** |
| COLLAB-003 | P1 | ~~无 session actor SSOT~~ **done (C1)** |
| COLLAB-004 | P1 | ~~邀请无 deep link~~ **done (C2)** |
| COLLAB-005 | P1 | ~~无 Client/Reviewer 角色化导航~~ **done (C3)** |
| COLLAB-006 | P2 | ~~ProjectEvent 无 member 级 attribution~~ **done (C3)** |
| SEC-001 | P0 | ~~无成员时 local-user 全权限 bootstrap~~ **mitigated (C1)** |
| SEC-002 | P1 | 无 OAuth；actor_id 可伪造 |
| APP-028 | P1 | ~~缺统一 require 门面~~ **done (C1)**；写路径 **done (C2)** |
| UI-010 | P1 | ~~无角色 chrome~~ **partial (C3 strip)**；全局顶栏切换仍薄 |
| BILL-001 | P2 | 无 token 聚合 / 项目用量 UI |
| BILL-002 | P2 | 无 seat / quota 模型 |
| DOM-032 | P2 | 无 Organization / tenant 根对象 |

---

## 专题衔接

| 专题 | 钩子 |
|------|------|
| 07 产品闭环 | continue_work 已接 `actor_id` 角色启发式（C3） |
| 01 Domain | 无 Org 根（DOM-032） |
| 04 设计循环 | Ask durable；Apply/选定/批准已可归因（C3） |
| module-audit | `15-collaboration` / `16-billing-usage` |

---

## 验收

- [x] 路径取证与理想对照  
- [x] Issue 登记 module-audit  
- [x] Phase C1 身份与可见项目  
- [x] Phase C2 写路径 RBAC + invite deep link  
- [x] Phase C3 角色化 UI（COLLAB-005）  
- [x] Phase C3 事件成员归因（COLLAB-006）  
- [ ] Phase C3 余量：用量 / tenancy
