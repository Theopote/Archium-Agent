# 第二轮-01：核心领域模型审计（Domain Model）

**日期：** 2026-07-26  
**范围：** `archium/domain/` 世界模型（非 `domain/visual` 版式几何）  
**核心问题：** Archium 有没有一个稳定的「世界模型」？

---

## 一句话结论

**有雏形，尚未成「稳定世界模型」。**

`Project` 已是真正的领域身份根（Pydantic + ORM），认知面（`KnowledgeState` / `ProjectContext`）与设计面（`ConceptDirection` → `DesignIntent` / Mission）已成型；但 Project **不拥有**完整聚合导航，过程/知识/决策/产物多为旁路指针或嵌套拷贝。继续堆 Research / CAD / BIM / 绘画而不先钉死边界，分裂风险真实存在。

---

## 理想结构 vs 现状

### 理想（产品叙事）

```text
                    Project
                       |
        --------------------------------
        |              |               |
 ProjectContext   DesignProcess   KnowledgeBase
        |              |               |
 KnowledgeState   DesignIntent    Evidence
                       |
              ----------------
              |              |
        ConceptDirection  DesignDecision
              |
        DesignArtifact
```

### 现状（代码）

```text
Project                          # 身份根 + 嵌套 KS / KS History / IntentEvolution
│
├── (FK 子表，不挂在 Project 对象上)
│     Mission(+嵌套 DesignIntent)
│     Fact / KnowledgeItem(+可选 DesignKnowledge)
│     ExplorationSession → ConceptDirection
│     Presentation… / ProjectEvent / ArtifactJob…
│
├── ProjectContext               # 运行时合成的认知读模型（无独立表）
└── ProjectProcessBoard          # 派生过程指针（无 DesignProcess 实体体）
```

| 理想节点 | 现状对应 | 成熟度 |
|----------|----------|--------|
| Project | `domain/project.py` + `ProjectORM` | **身份根可用**；字段仍偏「项目管理元数据」 |
| ProjectContext | `domain/context/project_context.py` | **认知读模型清晰**；故意不持过程 |
| KnowledgeState | `intent/knowledge_state.py`（嵌 Project） | **认知索引可用**；权威在 Fact/KnowledgeItem |
| DesignProcess | `ProjectProcessBoard` + `DesignProcessFocus` | **仅指针**；无过程实体体 |
| KnowledgeBase | `ProjectFact` + `ProjectKnowledgeItem` | **账本有**；无统一 KnowledgeBase 聚合 |
| DesignIntent | `intent/design_intent.py`（嵌 Mission） | **结构化意图可用** |
| ConceptDirection | `concept_direction.py` | **探索分支实体可用** |
| DesignRationale | `design_rationale.py` | **推理链字段已有**（observation→strategy） |
| DesignDecision | `spatial_design.DesignDecision` | **VO 有**；持久化为 `dict` 弱类型 |
| DesignArtifact | **缺失** | `ArtifactKind` 几乎全是汇报管线产物 |

---

## 检查项 1：Project 是数据库对象还是领域实体？

### 判定：**领域身份实体，但仍是「瘦根」**

```14:30:archium/domain/project.py
class Project(IdentifiedModel, TimestampedModel):
    """A building or planning project that owns documents and presentations."""
    name: str = ...
    ...
    knowledge_state: KnowledgeState | None = None
    knowledge_state_history: KnowledgeStateHistory = ...
    intent_evolution: IntentEvolution = ...
```

| 期望能力 | 现状 |
|----------|------|
| identity | `id` + name/code/type/stage/status — **有** |
| context | **不嵌**；经服务合成 `ProjectContext` |
| intent | **不嵌**；在 Mission / ConceptDirection / IntentEvolution |
| knowledge | **索引嵌套**（KS）；正文在 Fact/KnowledgeItem 表 |
| decisions | IntentEvolution + ProjectEvent；Decision 常为 dict |
| artifacts | **无设计产物聚合**；汇报 Artifact 另轨 |
| history | KS History + IntentEvolution + ProjectEvent — **多轨** |

**行为：** 仅有 `archive` / `mark_deleting` / `touch`，几乎无建筑领域不变量方法。

**风险：** 新能力若只看到「Project = 行 + JSON」，会各自再建 ResearchProject / VisualProject。当前 FK 纪律尚在，但 **缺少显式 Aggregate 地图**（哪些必须经 Project，哪些禁止旁路）。

---

## 检查项 2：对象关系 — 循环依赖？

### Import 图：**基本无环**（健康）

```text
Project → KnowledgeState / KnowledgeStateHistory / IntentEvolution
ProjectContext → KnowledgeState（只读嵌入读模型）
ProjectMission → DesignIntent → DesignRationale / SpatialIntent / DesignRule
ConceptDirection → DesignRationale / SpatialIntent / DesignRule / ConceptVisualPrompt
```

引用多为 `project_id: UUID`，符合「引用优于深嵌」。

### 语义风险（比 import 循环更危险）

| 风险 | 说明 | 建议 |
|------|------|------|
| **VO 双份嵌套** | `DesignRationale` / `SpatialIntent` / `DesignRule` 同时嵌在 ConceptDirection 与 DesignIntent | Mission commit 后方向与意图可漂移；应用层需显式同步契约，或改为「方向持有、意图引用 direction_id」 |
| **Decision 弱类型** | `IntentEvolutionEvent.design_decision: dict` | 写入/读出统一 `DesignDecision`，dict 仅作迁移兼容 |
| **KS 回声字段** | KS 上 `lifecycle_stage` / `recommended_workflow` / `primary_page_key` 与 ProjectContext 同义 | 权威定在 Context 合成结果；KS 只存索引与 dimensions |
| **命名碰撞** | `ProjectMission.project_context: str` ≠ `ProjectContext` | 重命名叙事字段（如 `task_context_narrative`） |
| **废弃双写** | Mission `key_unknowns` / `confidence` vs 活 KS | 已标注 deprecated；产品路径禁止再当活认知读 |

**结论：** 无危险的对象环；真正问题是 **拷贝嵌套 + 多源真相**。

---

## 检查项 3：各核心对象评级

| 对象 | 类型 | 评级 | 一句话 |
|------|------|------|--------|
| Project | 实体 + ORM | B | 身份根对；聚合导航弱 |
| ProjectContext | 派生读模型 | A- | 四问清晰，故意不上帝化 — **正确** |
| KnowledgeState | VO 索引 | A- | 多维认知成熟；权威正文在账本 |
| ProjectMission | 版本化实体 | A- | 任务定义稳；勿再塞活认知 |
| DesignIntent | VO | B+ | 结构够；无独立 id/project_id |
| ConceptDirection | 实体 | A- | 探索分支模型健康 |
| DesignRationale | VO | A- | 已具备推理链字段（第二轮-03 可复用） |
| DesignDecision | VO→dict | C+ | 类型有、持久化弱 |
| DesignKnowledge | VO | B+ | 护城河雏形；缺图边（→专题 02） |
| Artifact* | 汇报管线 | C | 名是 Artifact，实是 PPT 链 |
| ProjectProcessBoard | 派生指针 | B | DesignProcess 有相位无过程体 |

---

## 检查项 4：分裂风险（Research / Presentation / Visual 各自 Project？）

| 信号 | 现状 | 危险度 |
|------|------|--------|
| 多套 Project 表 | **无**；统一 `projects` | 低 |
| 旁路「伪 Project」DTO | `ProjectContextBundle`（RAG）、`ProjectOverview`（UI）等 | 中（命名混淆） |
| Stage 三词表 | `ProjectStage` / `ProjectLifecycleStage` / `KnowledgeMaturityStage` | 中 |
| Evidence 多形状 | IntentEvidence / EvidenceItem / list\[str\] / EvidenceSlot… | **高**（专题 02/03） |
| domain/visual 体量 | 远大于建筑世界模型核心 | **高**（工具型惯性） |
| Artifact 语义 | 汇报产物 vs 设计产物未分 | 高（专题 05/06） |

**当前未分裂，但边界文档不足。** 新 BIM/CAD 若再建一套 identity，会立刻裂开。

---

## 检查项 5：与「建筑设计智能体」的差距

已具备（智能体侧）：

- 认知连续谱（KnowledgeDimensions + NBA）
- 概念探索 → 方向 → Intent/Mission
- 设计推理字段（Rationale observation→strategy）
- 设计史边（IntentEvolution）
- 过程指针板（ProcessBoard）

仍偏工具侧：

- Project docstring 仍写 “owns documents and presentations”
- Artifact 权威表几乎全是 Outline/Layout/Scene/PPTX
- `VisualIntent` 绑在 **slide_id**（页级汇报意图），不是建筑 VisualIntent（场地/相机/建筑元素）——专题 06
- 无统一 `DesignArtifact` / `ArchitecturalAsset`

---

## 建议世界模型纪律（不要求立刻大拆）

### 1. 钉死聚合地图（文档 + 守卫即可先落地）

```text
Project（唯一 identity）
  ├── Cognition: KnowledgeState（持久）→ ProjectContext（派生）
  ├── Process:   ProjectProcessBoard（派生指针）
  ├── Knowledge: Fact / KnowledgeItem（FK）  ← KnowledgeBase 语义
  ├── Design:    Session → ConceptDirection → (commit) Mission.DesignIntent
  ├── Memory:    IntentEvolution / ProjectEvent / KS History
  └── Delivery:  Presentation…（汇报 BC，不得反向定义 Project）
```

禁止：新能力新建第二套 Project identity（含「LogicalProject」「WorkspaceProject」长期实体）。

### 2. 引用优于拷贝

- ConceptDirection → DesignIntent：**同步契约**或 **intent 只存 direction_id + 覆盖层**
- DesignDecision：持久化类型化
- Evidence：专题 02 收敛为少量权威形状 + adapter

### 3. 补齐两个缺失名（可渐进引入）

| 名 | 用途 | 注意 |
|----|------|------|
| `DesignArtifact`（或 `ArchitecturalArtifact`） | 概念图、分析图、空间模型、批判报告等设计产物 | **不要**与汇报 `ArtifactKind` 混表混枚举 |
| `ArchitecturalAsset` | PDF/CAD/BIM/照片统一入口（专题 05） | 与现有 SourceDocument 衔接，勿平行身份 |

### 4. 不做什么

- 不要把 Mission / Direction / Presentation **嵌回** Project 上帝对象
- 不要把 ProcessBoard **并入** ProjectContext（现设计正确）
- 不要为世界模型再开第七个 Agent 类

---

## 可行动 Issue（登记 module-audit `DOM-*`）

| 建议编号 | 级别 | 问题 |
|----------|------|------|
| DOM-023 | P1 | 缺少正式 Aggregate 地图；新能力易旁路 Project |
| DOM-024 | P1 | ConceptDirection 与 DesignIntent 共享 VO 双份嵌套，无同步不变量 |
| DOM-025 | P2 | DesignDecision 仅以 dict 挂 IntentEvolution |
| DOM-026 | P2 | `Mission.project_context` 字符串与 `ProjectContext` 同名异义 |
| DOM-027 | P1 | 无设计产物聚合；`ArtifactKind` 汇报偏置掩盖 DesignArtifact |
| DOM-028 | P2 | KnowledgeState 回声 lifecycle/workflow/page 与 Context 双写 |

（逐条字段表写入 `docs/audit/module-audit/02-domain.md`。）

---

## 专题衔接

| 下一专题 | 本审计已暴露的钩子 |
|----------|-------------------|
| 02 知识模型 | `DesignKnowledge` 字段接近护城河，缺 Graph 边与 precedent 结构 |
| 03 推理链 | `DesignRationale` + `ContextAssessmentReason` 已有；缺统一 Reasoning Artifact 身份 |
| 04 设计循环 | `DesignCritiqueReport` / Reflection 存在；与 Decision→Revise 闭环待查 |
| 05 多模态 | SourceDocument 有；ArchitecturalAsset 无 |
| 06 AI 绘画 | `ConceptVisualPrompt` / 页级 `VisualIntent` 分裂 |
| 07 产品闭环 | NBA + ProcessBoard 是基础；旅程完整性待查 |
| 08 协作 | `access.ProjectMember` 有雏形；Organization/角色权限待查 |

---

## 验收（本专题）

- [x] 核心对象清单与路径核对  
- [x] Project 瘦根 vs 理想聚合对比  
- [x] 循环依赖 / 双写风险列出  
- [x] 分裂风险评级  
- [x] 修复纪律与 DOM Issue 草案  
- [ ] DOM-023…028 合入 module-audit 台账并择优排期（下一步）
