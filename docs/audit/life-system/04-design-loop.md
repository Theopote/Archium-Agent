# 第二轮-04：设计循环审计（Create → Critique → Revise）

**日期：** 2026-07-26  
**范围：** IdeaSeed / ConceptDirection / DesignCritique / design_revise / Reflection / IntentEvolution / ProcessBoard / NBA / Presentation 入口  
**核心问题：** Archium 有没有真正的建筑设计循环，还是「选定瞬间的一次批判补丁」？

**前置：** Topic 03 已落地 R1–R3（链字段、ReasoningArtifact、`revise_direction_from_critique`）。本专题审计**循环形态**，不重复推理字段对齐。

---

## 一句话结论

**有 Critic→Revise→Re-Critique 路径，尚缺人工闸门与修订身份。**

Create 能产出可比较方向；选定前 Critique 能 warn/block；R3+L1 在选定瞬间可自动修订并 **再批判**，`verified` 仅在 proceed 后落下。仍缺：人工 Apply/Reject、Direction 修订代际、一等图 interrupt。ProcessBoard/NBA/Reflection 旁观路由而不驱动人闸。

---

## 理想循环 vs 现状

```text
理想：
  Create → Critique → (人) Revise → Re-Critique → Commit → …
                 ↑________________________|

现状：
  Create（方向卡片 ×N）
       ↓
  Critique-on-select（warn|block|off）
       ↓
  Auto-Revise（条件触发）→ Re-Critique（L1，默认 rules_only）
       ↓
  Select / Commit Mission（verified 仅 proceed）
       ↓
  Presentation soft-warn（reasoning unverified）
       ↓
  Narrative → Visual → PresentationCritic / DeckQA → Repair（另轨）
```

| 环节 | 成熟度 | 落点 |
|------|--------|------|
| Create | B+ | IdeaSeed → ConceptDirection×N；Mission 下亦可生成 |
| Critique（设计） | B | `DesignCritiqueService` 只读；选定门禁 |
| Critique（研究） | B- | `ResearchCritiqueService`；block 名不副实 |
| Revise | B- | `design_revise_service`；自动、启发式、无再验证 |
| Re-Critique | **B**（L1） | `run_design_loop_on_select` 修订后 rules 再批判 |
| 人工闸门 | **D** | Reflection UI 只展示；无 Apply |
| 过程编排 | C | ProcessBoard / NBA 旁路；非循环引擎 |
| 表达后批判 | B（另轨） | Visual/Deck QA + Repair ≠ Design Critic |

---

## 现状流水线（取证）

```text
[NBA / Genesis] → IdeaSeed
       ↓
 generate_directions → ConceptDirection×N
       (+ ensure rationale / reasoning / spatial)   ← Create 时静默补全
       ↓
 select_direction
       ├─ DesignCritiqueService.enforce_on_select
       ├─ _maybe_revise_from_critique → DIRECTION_REVISED / REFLECTION
       ├─ mark SELECTED
       ├─ IntentEvolution DIRECTION_SELECTED / DESIGN_DECISION
       └─（Mission 路径）design_intent_from_direction
       ↓
 commit_to_mission（探索）→ Mission + Intent 拷贝
       ↓
 presentation_cognition_gate：无 verified 推理 → 警告不阻断
```

### Create

- 探索：`ExplorationService.generate_directions`；Mission：`ConceptDirectionService.generate_directions`
- 主产物是**答案形方向卡片**，嵌套 Rationale / ReasoningArtifact（非独立 DesignArtifact，见 DOM-027）
- 生成时 `ensure_*` 已会补空链 / 空间——与 Revise 同类「静默写」，但发生在 Create

### Critique

| 通道 | 职责 | 改方向？ |
|------|------|----------|
| DesignCritique | 概念硬化前质疑 | **否**（席位契约） |
| ResearchCritique | 研究质量 | 否；block 仍落库 |
| VisualCritic / DeckQA | 表达/版面 | 否；**Repair** 另服务改稿 |

门禁：`DESIGN_CRITIQUE_ON_SELECT` = `off|warn|block`（默认 warn）。  
`block` + `reject` → `WorkflowError`。

### Revise（R3 已有）

- 触发：`chain_incomplete` / caution|reject / form_only / 非干净 proceed 的弱点缺证
- 补丁：回填空链槽、追加 risks / open_questions、启发式消化 `next_adjustments`，再 `ensure_*`
- **不**改 title/theme 正文；**不**编造面积指标；探索选定后 Intent 要等 commit 才拷贝（放大 DOM-024）
- `verified` 可在 proceed 或链补全后软标记——再批判缺失使「verified」偏乐观

### 循环缺口（本专题焦点）

1. ~~无 Re-Critique~~ → **L1 已闭合**（修订后 rules 再批判）  
2. **无人工 Apply**：自动修订仅以 warning 字符串通知（APP-013）  
3. **Reflection UI 只读**：`apply_reflection_adjustments` 无产品入口（APP-014）  
4. **Mission 路径初评不记 DESIGN_CRITIQUE 边**（修订后再批判会记；APP-015）  
5. **非工作流图**：循环挂在 `select_direction` 服务调用上（WF-009）

---

## 旁路：ProcessBoard / NBA / Reflection

| 产物 | 与循环关系 |
|------|------------|
| ProcessBoard | 只读相位指针（exploring→comparing→selected…）；**不执行** Create/Critique/Revise |
| NBA / Context | 可路由进入 Create / Research；**不驱动** Critique↔Revise |
| DesignReflection | 由批判派生；调整项已可被 Revise 消化，UI 仍不能点选执行 |
| IntentEvolution | 历史图（含 `DIRECTION_REVISED`）；可观测，非控制面 |

Topic 03 已约定：**不**把 ProcessBoard 并进 ProjectContext。本专题维持——循环应成为显式用例/图节点，而非塞进认知聚合。

---

## 静默改写风险盘点

| 来源 | 风险 |
|------|------|
| Create 时 `ensure_rationale/reasoning/spatial` | 空槽被合成，看似「模型想过」 |
| Select 时 auto-revise | Critic 只读契约下，系统仍改方向字段 |
| `verified_after_chain_fill` | caution 下链补全即 verified，跳过再批判 |
| Deck Repair（另轨） | 用户感知「系统改了我的稿」——与设计循环混淆（APP-004/005） |

Critic 席位本身干净；循环层的「自动修订」是产品策略问题，不是把改写塞回 Critic 服务。

---

## 亮点（勿推倒）

1. Design Critic 与 Revise **分服务**——符合六席位 / 不静默重写甲板的契约  
2. R3 已有可测的 `revise_direction_from_critique` + IntentEvolution 边  
3. ReasoningArtifact + chain 门禁让批判有结构靶子  
4. 探索可换方向再走批判（commit 前）；Mission 可换 sibling  
5. 汇报入口对未验证推理软警告（Beta 正确：不硬挡）  
6. Research Critic 与 Design Critic 分轨——正确

---

## 建议演进（渐进）

### Phase L1 — 闭合再验证（P0）✅ 2026-07-26

1. Revise 后 **强制再跑一次** `critique`（默认 `rules_only`；reject 仍走 warn/block）  
2. `verified=true` **仅**在权威批判 `proceed` 后设置（初评无修订，或修订后再批判）  

实现：`archium/application/design_loop.py` → `run_design_loop_on_select`；探索/Mission 选定路径共用。  
（关闭 `APP-012`。）

### Phase L2 — 人工闸门（P1）

3. 选定流拆成：Critique 报告 → UI Apply/Reject adjustments → 再 Select  
4. `DESIGN_REVISE_ON_SELECT=off|auto|ask`（默认 ask 或保持 auto + 显式 diff）  

### Phase L3 — 循环身份（P2）

5. Direction revision 指针（`parent_reasoning_id` / revision n）或薄 DesignArtifact 挂 CritiqueReport  
6. 可选：探索图 interrupt 节点（不新 Agent）；Mission 路径补齐 `DESIGN_CRITIQUE` 边  

**不做：** `DesignLoopAgent`；把 Deck Repair 并进 Design Critic；ProcessBoard 变写权威。

---

## 可行动 Issue

| 编号 | 级别 | 问题 |
|------|------|------|
| APP-012 | P1 | ~~Revise 后无再 Critique~~ **done (L1)** |
| APP-013 | P1 | 选定路径自动修订无人工确认（相对 Critic 只读契约的产品缺口） |
| APP-014 | P2 | Reflection `next_adjustments` UI 无 Apply/Reject |
| APP-015 | P2 | Mission `select_direction` 不写 IntentEvolution `DESIGN_CRITIQUE` 边 |
| APP-016 | P2 | Research Critic `block` 不拒绝落库 / 不挡概念硬化 |
| DOM-030 | P2 | 批判/修订结果缺少 Direction 修订身份（diff / parent） |
| WF-009 | P2 | 设计循环非一等图节点（无 critique→human→revise→re-critique interrupt） |
| DOM-024 | P1 | （已有）Direction↔Intent 双份；revise-then-commit 放大漂移 |
| DOM-027 | P1 | （已有）CritiqueReport/Reflection 非 DesignArtifact |
| APP-004 | P1 | （已有）设计批判与版面 QA/Repair 权威需继续隔离 |

（写入 `03-application.md` / `02-domain.md` / `04-workflow.md`。）

---

## 专题衔接

| 专题 | 钩子 |
|------|------|
| 03 推理链 | R3 提供 Revise 原子能力；04 证明仍缺迭代与人闸 |
| 01 Domain | DOM-024/027/030：循环产物无处安放 / 双份意图 |
| 02 Knowledge | Research Critic 另轨；证据进 Design Critic 摘要 |
| 05 多模态 | Create 输入变宽后，循环闸门更关键 |
| 06 绘画 | Visual Critic/Repair 必须继续与设计循环分轨 |
| 07 产品闭环 | 选定→汇报的「一次通过」体验 vs 设计迭代预期 |

---

## 验收（本专题）

- [x] Create / Critique / Revise 三环取证  
- [x] 与理想迭代循环对照；判定 one-shot  
- [x] 静默改写与旁路（ProcessBoard/NBA）边界说明  
- [x] Issue 草案 APP-012…016 / DOM-030 / WF-009  
- [x] 择优落地 Phase L1（再批判 + verified 收紧）
