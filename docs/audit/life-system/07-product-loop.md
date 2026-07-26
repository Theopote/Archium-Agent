# 第二轮-07：产品闭环审计

**日期：** 2026-07-26  
**范围：** 导航脊柱 / ProcessBoard / Orchestration / 人闸 / Mission→Presentation bridge / 跨会话恢复  
**核心问题：** 子系统（设计循环、多模态、Vision、LangGraph 门禁）已可用时，用户是否走得通一条**可感知、可恢复**的建筑设计智能体闭环？

**前置：** Topic 04 L1–L3、05 M1–M3、06 P1–P3 已闭合。本专题查**产品胶合层**，不重复子系统字段审计。

---

## 一句话结论

**子系统可用；L1 后「继续工作」不再过早跳进汇报链。** 设计 Ask/批判仍多停在 session；ProcessBoard/Orchestration 尚未成为单一 stage truth（WF-010）。

---

## 理想 vs 现状

```text
理想：
  Genesis/NBA
       ↓
  Explore → Critique/Ask/Revise → Select
       ↓
  Mission + Workstream (+ Research)
       ↓
  Evidence (materials) → Vision (Brief/DesignArtifact)
       ↓
  Outline → Generate → Studio → Deliver
       ↑________人闸 / 编排 interrupt________|

现状：
  [Strong subgraphs]              [Weak product glue]
  design_loop L1–L3               dual nav（五阶段 vs 隐藏设计页）
  vision P1–P3                    continue_work 过早进汇报链
  LangGraph review interrupts     Ask/critique 多 session-only
  IntentEvolution 边（DB）         UI 常读 session 不读边
  ProcessBoard（只读派生）         不进 stepper / stage gate
  Orchestration（局部 UI）         非主 driver
```

| 层 | 成熟度 | 落点 |
|----|--------|------|
| 汇报五阶段 | B+ | `product_flow` + `flow/*` + stage gate |
| 设计/使命页 | B | genesis / concept-exploration / project-mission（**hidden**） |
| Mission→汇报桥 | B- | `mission_to_presentation_request`；主链曝光弱 |
| 人闸（汇报/Visual） | B | LangGraph interrupt + checkpoint |
| 人闸（设计 Ask） | C | session `pending_design_revise` |
| 进度 SSOT | D | 五阶段 / ProcessBoard / Orchestration **三套并存** |
| 跨会话恢复 | C+ | Direction/Brief/Asset ✅；Ask/critique UI ❌ |

---

## 亮点（勿推倒）

1. 正式五阶段与 Studio/交付门禁成熟，适合「有 Brief 后的汇报制作」  
2. Design loop / Vision / 多模态在服务层已闭合，可被产品胶合而不必重写  
3. Planning / Presentation / Visual 图已有真实 interrupt + checkpoint  
4. ProcessBoard / NBA / HumanGate 词汇表已在，缺的是**接到主 chrome**

---

## 裂缝取证（摘要）

### 1. 双轨导航

侧栏：`materials → outline → generate → edit → deliver`  
深链：`project-genesis` / `concept-exploration` / `project-mission`  

`continue_work_page_key`：仅当 `slide_count<=0` **且** `not has_mission_or_task` 才读 workflow entry；一旦有 Mission/任务描述，即使用户仍在比较方向，也会跳进汇报阶段。

### 2. 三套进度

| 模型 | 控制面？ | UI |
|------|----------|-----|
| 产品五阶段 | **是**（stepper / gate） | 侧栏主链 |
| ProcessBoard | 否（只读派生） | knowledge profile expander |
| OrchestrationPlan | 局部（Mission 面板） | `orchestration_status` |

`evaluate_stage_gate` 不查 ConceptDirection 选定、推理 verified、VisualConceptBrief / DesignArtifact。

### 3. 人闸可恢复性

| 闸 | 持久？ |
|----|--------|
| Brief/Storyline/Outline/Visual interrupt | WorkflowRun checkpoint ✅ |
| Design Ask / pending revise | session ❌ |
| `last_design_critique_report` | session ❌（Deliver 卡不 Hydrate IntentEvolution） |

### 4. 已有但弱曝光

- `mission_to_presentation_request` / `mission_context_bridge`  
- `presentation_cognition_gate`（默认 warn；与 stage gate 未合并）  
- DesignArtifact 在 Asset.metadata（Topic 06）；Deliver/主 nav **无设计产物板**  
- MS-002：Presentation 无持久 `mission_id`

---

## 建议演进

### Phase L1 — 导航脊柱（P1）✅ 2026-07-26

1. **统一继续工作**：`resolve_continue_work_page_key` 优先 unresolved design + 设计侧 Orchestration，再 NBA entry / 五阶段  
2. **Stepper soft-guide**：materials/outline gate 警告仍在比较方向  
3. **常驻 design strip**：`render_design_context_strip` 展示 ProcessBoard.label + 深链  

（关闭 `UI-007` / `UI-008`；`WF-010` 仍开。）

### Phase L2 — 可恢复人闸（P1–P2）

4. 持久化 `pending_design_revise`（Exploration/Mission metadata 或 ProjectEvent）  
5. Deliver/Outline Hydrate 最近 `DESIGN_CRITIQUE` 边 → 可行动 NBA  
6. Stage gate 合并 cognition gate warnings（默认仍 warn）

（关闭草案 `APP-026` / `APP-027`；`UI-009`。）

### Phase L3 — 端到端 lineage（P2）

7. Presentation.`mission_id`（**MS-002**）+ bridge 默认注入  
8. materials/deliver **DesignArtifact 时间线**  
9. Research → 页引用链（接既有 DOM/KN 债）  
10. Critique 分轨行动：设计→回探索；版面→Studio（强化 **APP-004**）

**不做：** 新 Agent；ProcessBoard 写进 ProjectContext 当 SSOT；把设计循环硬塞进 LangGraph。

---

## 可行动 Issue

| 编号 | 级别 | 问题 |
|------|------|------|
| UI-007 | P1 | ~~五阶段与 ProcessBoard 脱节~~ **done (L1)** |
| UI-008 | P1 | ~~无常驻方向/Mission 条~~ **done (L1)** |
| WF-010 | P2 | OrchestrationPlan 与 product_flow 双轨；缺单一 stage truth |
| APP-026 | P1 | pending_design_revise / critique UI 仅 session；闭环不可恢复 |
| APP-027 | P2 | 设计批判未 Hydrate 到 Deliver/Outline；不驱动 NBA |
| UI-009 | P2 | Orchestration HumanGate 未在五阶段顶栏统一展示 |
| MS-002 | P1 | （已有）Presentation 无持久 mission_id |
| DOM-024 | P1 | （已有）Direction↔Intent 双份漂移放大闭环断裂 |
| APP-004 | P1 | （已有）QA 多栈；交付门禁需统一 verdict |
| UI-006 | P1 | （已有）剧本 E 真人闭环验收未完成 |

---

## 专题衔接

| 专题 | 钩子 |
|------|------|
| 04 设计循环 | 后端闭合；产品 Ask 不可恢复 |
| 05 多模态 | 证据进 Context；与 design 阶段门禁未串联 |
| 06 绘画 | DesignArtifact 有身份；主 nav 无产物视图 |
| 01 Domain | DOM-024 放大 commit 后语义断裂 |
| 08 商业化 | 可续闭环是协作/计费前提 |

---

## 验收

- [x] 路径取证与理想对照  
- [x] Issue 草案登记 module-audit  
- [x] Phase L1 导航脊柱  
- [ ] Phase L2 可恢复人闸  
- [ ] Phase L3 lineage（含 MS-002）
