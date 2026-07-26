# 第二轮-07：产品闭环审计

**日期：** 2026-07-26  
**范围：** 导航脊柱 / ProcessBoard / Orchestration / 人闸 / Mission→Presentation bridge / 跨会话恢复  
**核心问题：** 子系统（设计循环、多模态、Vision、LangGraph 门禁）已可用时，用户是否走得通一条**可感知、可恢复**的建筑设计智能体闭环？

**前置：** Topic 04 L1–L3、05 M1–M3、06 P1–P3 已闭合。本专题查**产品胶合层**，不重复子系统字段审计。

---

## 一句话结论

**子系统可用；Topic 07 产品闭环胶合层可走通。** 继续工作尊重设计态；Ask/批判可恢复；汇报可溯源 Mission；五阶段 HumanGate；单一 stage；Direction↔Intent 可 diff；导出只读 `ExportVerdict`；Scene 修后 Plan 一致；Research→页引用经 `resolve_citations` 投影。

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
| 人闸（设计 Ask） | **B（L2）** | `IntentEvolution.pending_design_revise` |
| 进度 SSOT | D | 五阶段 / ProcessBoard / Orchestration **三套并存** |
| 跨会话恢复 | **B（L2）** | Direction/Brief/Asset ✅；Ask/critique UI ✅ |

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
| Design Ask / pending revise | **IntentEvolution.pending_design_revise ✅（L2）** |
| `last_design_critique_report` | session + **IntentEvolution DESIGN_CRITIQUE hydrate ✅** |

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

（关闭 `UI-007` / `UI-008`；`WF-010` 后补 done。）

### Phase L2 — 可恢复人闸（P1–P2）✅ 2026-07-26

4. `IntentEvolution.pending_design_revise` 持久化 Ask；UI hydrate + Apply/Reject 清除  
5. Deliver/Outline 从 DESIGN_CRITIQUE 边 / pending hydrate；caution/reject 链回概念探索  
6. materials/outline stage gate 合并 cognition readiness warnings（默认仍 warn）  

（关闭 `APP-026` / `APP-027`；`UI-009` 后补 done。）

### Phase L3 — 端到端 lineage（P2）✅ 2026-07-26

7. `Presentation.mission_id` + `PresentationRequest.mission_id`（**MS-002**）；Mission bridge / create / workflow serialize 注入  
8. materials/deliver **DesignArtifact 时间线**（`design_artifact_catalog`）  
9. Research → 页引用链：**done** — `SlideSpec.source_citations: SourceCitation`；`research_page_citation_bridge` 挂 `enrich_slide_citations`（DOM-008/KN-002 全量仍开）  
10. Critique 分轨：设计→回探索（L2）；Deliver 加「回工作室」链（弱化 APP-004，不关）

（关闭 `MS-002`；`UI-009` / `WF-010` / `DOM-024` / `APP-004` **done**；Research→页引用 **done**。）

### Phase L3+ — HumanGate 顶栏 ✅ 2026-07-26

11. **UI-009**：`render_orchestration_status(compact=True)` 接入 `render_stage_header`；五阶段可见待确认 + Continue/Replan

### Phase L3++ — 单一 stage truth ✅ 2026-07-26

12. **WF-010**：`resolve_product_stage_truth` — 活跃编排映射五阶段，覆盖 presentation 启发式；snapshot `authoritative_stage_id`

### Phase L3+++ — Direction↔Intent 同步 ✅ 2026-07-26

13. **DOM-024**：`DesignIntent.source_direction_id` + `diff_direction_intent`；投影后对齐 / 漂移可检

### Phase L3++++ — 导出统一 verdict ✅ 2026-07-26

14. **APP-004**：QA 多栈只产证据；`export_gate` + `ExportVerdict.evidence_stacks`；Studio/Deliver 导出只读 verdict

### Phase L3+++++ — Research→页引用 ✅ 2026-07-26

15. 已确认 Research `SourceCitation`（含 URL）经 `attach_research_citations_to_slide` → `SlideSpec`；导出 `citation_lines_for_slide` 可读 label

**不做：** 新 Agent；ProcessBoard 写进 ProjectContext 当 SSOT；把设计循环硬塞进 LangGraph。

---

## 可行动 Issue

| 编号 | 级别 | 问题 |
|------|------|------|
| UI-007 | P1 | ~~五阶段与 ProcessBoard 脱节~~ **done (L1)** |
| UI-008 | P1 | ~~无常驻方向/Mission 条~~ **done (L1)** |
| WF-010 | P2 | ~~OrchestrationPlan 与 product_flow 双轨~~ **done** |
| APP-026 | P1 | ~~pending Ask 仅 session~~ **done (L2)** |
| APP-027 | P2 | ~~批判未 Hydrate~~ **done (L2)** |
| UI-009 | P2 | ~~Orchestration HumanGate 未在五阶段顶栏~~ **done** |
| MS-002 | P1 | ~~Presentation 无 mission_id~~ **done (L3)** |
| DOM-024 | P1 | ~~Direction↔Intent 双份漂移~~ **done（source_direction_id + diff）** |
| APP-004 | P1 | ~~QA 多栈；交付门禁需统一 verdict~~ **done**（`export_gate` + `evidence_stacks`） |
| UI-006 | P1 | （已有）剧本 E 真人闭环验收未完成 |

---

## 专题衔接

| 专题 | 钩子 |
|------|------|
| 04 设计循环 | 后端闭合；Ask 已 durable（L2） |
| 05 多模态 | 证据进 Context；与 design 阶段门禁软串联 |
| 06 绘画 | DesignArtifact 有身份 + materials/deliver 时间线 |
| 01 Domain | DOM-023 / DOM-024 已落地；DOM-025…028 仍开 |
| 08 商业化 | 可续闭环已是协作/计费前提（Topic 08 完成） |

---

## 验收

- [x] 路径取证与理想对照  
- [x] Issue 草案登记 module-audit  
- [x] Phase L1 导航脊柱  
- [x] Phase L2 可恢复人闸  
- [x] Phase L3 lineage（MS-002 + DesignArtifact 板；Research→页引用桥接）  
- [x] UI-009 五阶段 HumanGate compact 顶栏  
- [x] WF-010 单一 product stage truth  
- [x] DOM-024 Direction↔Intent sync / diff  
- [x] APP-004/005 + DOM-023  
- [x] Research→页引用（`research_page_citation_bridge`；DOM-008 全量仍开）
