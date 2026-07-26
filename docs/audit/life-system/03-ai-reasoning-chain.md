# 第二轮-03：AI 推理链审计

**日期：** 2026-07-26  
**范围：** agents / workflow / DesignRationale / Critique / Reflection / ContextAssessment / IntentEvolution  
**核心问题：** Archium 是在「生成答案」，还是在「生成设计推理」？

---

## 一句话结论

**意图是推理，运行时仍偏答案。**

`DesignRationale` 已有 observation→problem→hypothesis→strategy 槽位，建筑推理框架也注入 Prompt；但 LLM draft **不要求**写满推理链，Critic 能挡选不能改稿，Reflection 的 `next_adjustments` **不被执行**。没有一等公民 `ReasoningArtifact` 身份——推理多嵌在方向/意图里当 prompt 填料。

---

## 理想链 vs 现状

```text
理想：理解背景 → 发现问题 → 提出假设 → 形成策略 → 验证 → 表达

现状：
  ContextAssessmentReason     ✓ 认知路由可解释
  IdeaSeed                    △ 标签化，非问题链
  ConceptDirection 卡片       ★ 主产物（答案形）
  DesignRationale             △ 域有链，LLM schema 砍半；常靠 fallback 合成
  DesignCritique              ✓ 可选门禁；✗ 无 Revise
  DesignReflection            △ 派生视图；✗ next_adjustments 未落地
  Mission / Presentation      ★ 消费 to_prompt_block → 答案生成
```

| 理想步骤 | 成熟度 | 落点 |
|----------|--------|------|
| 理解背景 | B+ | ProjectContext / ContextAssessmentReason |
| 发现问题 | B | DesignIntent.problem_statement / Rationale.problem / DK.problem |
| 提出假设 | C | Rationale.hypothesis 有域无 LLM |
| 形成策略 | B | spatial_strategy / Rationale.strategy / DK.strategy（分散） |
| 验证 | C+ | Critique 门禁；无 Critic→Revise |
| 表达 | A-（答案偏置） | Narrative → Visual → Render |

---

## 关键发现：Schema 与 Domain 断裂

Domain（完整）：

```21:55:archium/domain/design_rationale.py
class DesignRationale(DomainModel):
    statement / reasons / evidence / alternatives
    observation / problem / hypothesis / strategy / risks
```

LLM Draft（R1 后已对齐）：

```28:70:archium/infrastructure/llm/concept_direction_schemas.py
class DesignRationaleDraft(BaseModel):
    statement / reasons / evidence / confidence / alternatives
    observation / interpretation / problem / hypothesis / strategy / risks
```

**R1–R3 已关：** Draft↔Domain、ReasoningArtifact、Critic→Revise 原子路径。  
**Topic 04：** 循环仍为 one-shot（无再批判 / 无人闸）— 见 [04-design-loop.md](04-design-loop.md)。

---

## 产物盘点

| 产物 | 身份 | 持久化 | Critic 用？ | Revise 用？ |
|------|------|--------|-------------|------------|
| DesignRationale | 嵌套 VO | Direction/Mission JSON | 是（证据/形式空转） | 否 |
| ContextAssessmentReason | KS 嵌套 | projects.knowledge_state | 否 | NBA 路由 |
| IntentEvolution | 项目日志 | projects.intent_evolution | 记快照 | 否（只历史） |
| DesignCritiqueReport | 报告 VO | 多为 session / 事件快照 | **自身即 Critic** | 门禁；不改方向 |
| DesignReflection | 派生 VO | 无表 | — | next_adjustments **未执行** |
| ResearchRun | 遥测 |  ephemeral | Research Critic 另轨 | 否 |
| DesignKnowledge | 研究洞察 | KnowledgeItem JSON | prompt 注入 | 软 |
| ReasoningArtifact | **薄封装** | Direction JSON envelope | 是（reasoning_id） | 是（R3 revise + verified） |

`archium/agents/` 以 Narrative/Brief planner 为主，**不**产出 observation→strategy；消费 `design_intent_block` 字符串。

---

## 产品流：哪里在推理，哪里在 dump

```text
Context Intelligence ──推理(NBA)──► IdeaSeed
                                      │
                         ConceptDirection × N  ◄── Framework 在 system prompt
                         （答案卡片为主 + 可选 rationale）
                                      │ select
                         DesignCritique 门禁 ──► block/warn
                         DesignReflection（仅展示）
                                      │ commit
                         Mission.DesignIntent（拷贝方向）
                                      │
                         Brief/Outline/Slides/Vision
                         ◄── to_prompt_block 填料；不再验证推理链
```

**判定：** 认知面（Context）与研究面（DesignKnowledge）推理结构较强；**概念→汇报主链**仍是「生成可讨论的答案卡片」，推理是旁注。

---

## 与理想 Reasoning Artifact 对照

理想：

```json
{
  "observation": "基地位于山地",
  "interpretation": "需要减少人工切割",
  "hypothesis": "建筑应成为地景的一部分",
  "strategy": "低体量嵌入式布局",
  "evidence": { "cases": ["case:…"], "research": ["knowledge:…"] }
}
```

| 理想字段 | 最近似 | 缺口 |
|----------|--------|------|
| observation | Rationale.observation | LLM 不写；fallback≈idea |
| interpretation | **缺失** | 无类型字段 |
| hypothesis | Rationale.hypothesis | 同上 |
| strategy | 三处分散 | 无单一节点绑 problem→strategy |
| evidence.cases | reference_case_ids / precedent_ref | 未并入同一推理身份 |
| evidence.research | Rationale.evidence[] / IntentEvidence | 异构；KN-012 后设计链已清晰 |

另缺：独立 `id` / `project_id` / 版本 / 指向 Direction·Mission 的 FK / Critic 强制完整度 / Revise 同节点改写。

---

## 亮点（勿推倒）

1. Domain `DesignRationale` 链字段已就绪 — Topic 03 首选复用，不必另造上帝对象  
2. `ARCHITECTURAL_REASONING_FRAMEWORK` 明确禁止「先漂亮方案」  
3. Design Critic 五问（Why / Evidence / Problem fit / Alternative / Form-only）可 block  
4. DesignKnowledge / ArchitectureCase 研究侧 problem→strategy 已结构化（Topic 02）  
5. IntentEvolution 已能记 Trigger→Old→New→Reason  
6. ContextAssessmentReason 让 NBA 可解释（认知推理，与设计推理分轨正确）

---

## 建议演进（渐进）

### Phase R1 — 对齐 LLM 与 Domain（低成本，P0）✅ 2026-07-26

1. `DesignRationaleDraft` 增加 observation / problem / hypothesis / strategy（+ 可选 interpretation）  
2. Prompt 字段映射改为「Step → Rationale 链」，方向卡片字段为表达层  
3. Fallback 仅在链字段全空时启用；有 LLM 链则禁止静默覆盖  

（关闭 `APP-008` / `APP-009` / `DOM-029`。）

### Phase R2 — Reasoning 节点身份（中）✅ 2026-07-26

4. 薄封装 `ReasoningArtifact` = DesignRationale + `id` + `project_id` + evidence refs（cases / knowledge ids）  
   嵌套于 Direction 的 `design_rationale` JSON envelope（无新表）  
5. Critic 评分改为「链完整度 + 证据」；缺 hypothesis/strategy 不得 proceed  

（关闭 `APP-011`。）

### Phase R3 — Critic → Revise 闭环（产品关键）✅ 2026-07-26

6. `revise_direction_from_critique(report)`：写回同一 Direction 的 rationale / spatial / risks  
7. Reflection.`next_adjustments` 变为可执行建议（选定路径自动应用 + IntentEvolution `DIRECTION_REVISED`）  
8. Presentation 入口检查：无已验证 Reasoning 节点则警告（非硬挡 Beta）  

（关闭 `APP-010`。）

**不做：** 新 `ReasoningAgent` 类；把 ProcessBoard 并进 ProjectContext。

---

## 可行动 Issue

| 编号 | 级别 | 问题 |
|------|------|------|
| APP-008 | P1 | ~~DesignRationaleDraft 缺链字段~~ **done (R1)** |
| APP-009 | P1 | ~~框架映射到分散字段~~ **done (R1)** |
| APP-010 | P1 | ~~Critic/Reflection 无 Revise~~ **done (R3)** |
| APP-011 | P2 | ~~无 ReasoningArtifact~~ **done (R2)** |
| DOM-029 | P2 | ~~缺 interpretation~~ **done (R1)** |

（写入 `03-application.md` / `02-domain.md`。）

---

## 专题衔接

| 专题 | 钩子 |
|------|------|
| 01 Domain | Rationale 嵌套双份（DOM-024）放大「无推理 SSOT」 |
| 02 Knowledge | Case/DK 已是证据源；缺绑进 Reasoning 节点 |
| 04 设计循环 | 本专题证明 Critic/Revise 有、**迭代与人闸无** — 见 [04](04-design-loop.md) |
| 06 绘画 | Visual 吃 rationale prompt block，非验证后的推理节点 |

---

## 验收（本专题）

- [x] 推理产物与流水分盘点  
- [x] 生成答案 vs 设计推理判定  
- [x] Schema/Domain 断裂取证  
- [x] Issue 草案 APP-008…011 / DOM-029  
- [x] 择优落地 Phase R1（Draft 对齐）
