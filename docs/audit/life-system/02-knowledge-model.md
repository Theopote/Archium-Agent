# 第二轮-02：建筑知识模型审计

**日期：** 2026-07-26  
**范围：** DesignKnowledge / ArchitectureCase / Fact / Knowledge Graph / Evidence / Research 写回  
**核心问题：** Archium 的护城河是「建筑设计知识结构」，还是只有 LLM + 扁平事实表？

---

## 一句话结论

**已越过「纯自由文本 dump」；Phase A–C 后具备可链接、可写案例、可持久确认边的知识脚手架。**

结构化槽位与 `precedent_ref` / `reference_case_ids` 已对齐；项目级 `architecture_cases` 可扩展；`knowledge_graph_edges` 保存确认关系。图仍非 Neo4j 产品级知识库，但已不再「关掉进程结构消失」。Evidence 多身份（KN-012）与案例库体量仍是后续债。

---

## 护城河对比

### 普通 AI

```text
王澍象山校园
→ 一段介绍文字
```

### Archium 应有

```text
象山校园
  ↓ 设计问题：现代建筑如何回应地域文化
  ↓ 策略：碎片化体量
  ↓ 空间：院落 + 路径
  ↓ 材料：瓦片再利用
  ↓ 可迁移：文化类建筑（边界：气候/尺度/制度）
```

### Archium 现状最接近处

`ArchitectureCase`（种子）已按该骨架写：

```49:67:archium/infrastructure/research/case_library/seeds.py
ArchitectureCase(
    id="ningbo_museum",
    name="宁波博物馆",
    architect="王澍",
    ...
    design_problem="如何让博物馆成为地方建造记忆的容器，而非国际风格展馆？",
    strategy="瓦爿墙与山体意象转译聚落肌理",
    spatial_logic="内部街巷与庭院穿插；展陈与漫游并行",
    material_language="回收砖瓦、竹模混凝土",
    ...
)
```

`DesignKnowledge`（研究写回）槽位接近，但缺显式 `problem` / `precedent_id`：

| 理想槽 | DesignKnowledge | ArchitectureCase |
|--------|-----------------|------------------|
| concept | `principle` / `topic` | `transferable_principles` |
| problem | **无独立字段** | `design_problem` |
| strategy | 并入 `principle` | `strategy` |
| spatial_pattern | `spatial_translation` | `spatial_logic` |
| material_expression | `material_strategy` | `material_language` |
| precedent | 无 FK；仅 `evidence` 字符串 | **自身即 precedent** |
| applicability | `applicability` | `risks`（兼用） |

**缺口：** Case → DK 可 `to_design_knowledge()`，但 **DK → Case 无 `case_id`**；ConceptDirection 的 `reference_dna` 是自由字符串，不是案例 ID。

---

## 现状分层图

```text
┌─────────────────────────────────────────────────────────────┐
│  读时投影（不持久）                                           │
│  KnowledgeGraphSnapshot ← KnowledgeGraphService.build_snapshot │
│  （Fact + KnowledgeItem 字段爆炸 + 全部 seed Case）            │
└────────────────────────────▲────────────────────────────────┘
                             │ 启发式边（slug 节点）
┌────────────────────────────┴────────────────────────────────┐
│  持久账本（扁平）                                             │
│  ProjectFact ──────────────── ProjectKnowledgeItem            │
│  （指标/约束）                 │ + design_knowledge JSON       │
│                               │ + Chroma vector index         │
└───────────────────────────────┼──────────────────────────────┘
                                │ 写回
┌───────────────────────────────┴──────────────────────────────┐
│  研究 / 案例入口                                               │
│  AutonomousResearch → ResearchFindingDraft → DesignKnowledge │
│  ArchitectureCase seeds（内存 8 条，不可用户写入）              │
└──────────────────────────────────────────────────────────────┘
                                │ prompt 注入
┌───────────────────────────────┴──────────────────────────────┐
│  设计消费面                                                   │
│  ConceptDirection（reference_dna 纯文本）                      │
│  DesignIntent.evidence（statement 拷贝，弱链接）               │
│  DesignRationale（推理链文本，无图边）                          │
└──────────────────────────────────────────────────────────────┘
```

---

## 检查项评级

| 能力 | 评级 | 说明 |
|------|------|------|
| 结构化设计知识 VO | **B+** | `DesignKnowledge` / `ArchitectureCase` 槽位对路 |
| 研究写回持久化 | **B** | 进 `ProjectKnowledgeItem.design_knowledge` JSON；有 Critic/映射 |
| 案例库 / Precedent | **C+** | 8 seeds、token 匹配、无象山、无 ORM、不可扩展 |
| Design Knowledge Graph | **C** | 类型与边枚举齐全；**不落库**；节点靠文本 slug |
| Fact 账本 | **A-** | 项目指标 SSOT 清晰（与设计知识应分工） |
| KnowledgeState 索引 | **A-** | 认知索引成熟；不是知识图谱 |
| Evidence 统一身份 | **D** | Intent / DK / Manuscript / Visual Slot / Pack 多世界（见下） |
| 与 Intent/Direction 硬链接 | **C** | 多为 prompt 注入与字符串拷贝 |

---

## Evidence 权威地图（KN-012 done）

| 链 | 权威类型 | 说明 |
|----|----------|------|
| **设计** | `IntentEvidence` + `SourceCitation` | 意图出处 / 知识引用；`IntentEvidence.knowledge_item_id` 可选硬链 |
| **汇报** | `PresentationEvidenceItem` / `Slot` / `Requirement` | 稿件与页模板；旧名 `Evidence*` 为别名 |
| **交付** | `MaterialsAvailability` / `MaterialsExportReadiness` / `ContextMaterialsPack` | 出门禁与 CI 材料信号；旧名 `EvidenceAvailability` 等为别名 |
| **非身份** | `DesignKnowledge.evidence` 等 `list[str]` | 仅标签，不是 Evidence 实体 |

代码 SSOT：`archium/domain/evidence_authority.py`。不改 `LayoutFamily.EVIDENCE_BOARD` 等 PPT 字符串契约。

---

## Evidence 分裂（历史表，已收敛命名）

| 形状 | 用途 | 是否设计知识边 |
|------|------|----------------|
| `IntentEvidence` | Mission 意图出处 | 弱（statement 拷贝） |
| `DesignKnowledge.evidence` | 短标签/URL | 字符串列表 |
| `DesignRationale.evidence` | 推理依据 | 自由文本 |
| `ProjectEvidencePack` | Context 评估材料信号 | 聚合，非图 |
| Manuscript `EvidenceItem` | 汇报论证目录 | **汇报遗留** |
| Visual `EvidenceSlot` / `EvidenceRequirement` | 页模板要图/指标 | **汇报遗留** |
| `RenovationEvidence` | 改造议题本地链 | 局部结构化 |
| Export `ProjectEvidenceStatus` | 出门禁 | 交付 |

**没有单一 Evidence 身份。** 「证据」一词被汇报管线占用，稀释了设计知识语义（与 DOM-027 Artifact 偏置同源）。

---

## 图系统：看起来像护城河，实际是检索加速器

`KnowledgeNodeKind` 含 CONCEPT / STRATEGY / MATERIAL / SPACE / CASE —— 产品叙事正确。

现实：

1. `build_snapshot(project_id)` **每次全量重建**
2. 边来自字段文本爆炸（`space:{slug}`），非策展三元组
3. `STRATEGY` kind 在枚举里，builder 主路径更偏 CONCEPT/SPACE/MATERIAL/TAG
4. 全库 seed Case 打进每个项目快照 —— 有利于检索，不是「项目知识积累」
5. 显式注释：*Not Neo4j*

**定位建议：** 短期保留为 Fusion/检索通道；中期若要护城河，需 **可写 Case + 类型化边（至少 DK↔Case、Problem↔Strategy）**，否则永远是「好看的 prompt 图」。

---

## 与理想护城河的差距清单

| # | 差距 | 影响 |
|---|------|------|
| 1 | DesignKnowledge 无 `problem` / `strategy` 分立（与 Case 不对齐） | 研究写回与案例库两套词表 |
| 2 | 无 `precedent_id` / `case_id` FK | 无法回答「这条洞察来自哪一案」 |
| 3 | `reference_dna` 自由字符串 | 概念方向无法回链案例库 |
| 4 | Case 仅内存 seeds、不可用户贡献 | 护城河无法随事务所增长 |
| 5 | Graph 不持久 | 关掉进程 = 知识结构消失 |
| 6 | Evidence 多身份 | 追溯与批判无法统一引用 |
| 7 | 无象山等关键文化案例深化 | 产品叙事与种子库落差 |

**不要做的：** 立刻上 Neo4j / 巨型案例爬虫。优先 **身份与链接**，再谈图数据库。

---

## 建议演进（渐进，不推翻）

### Phase A — 对齐词表与硬链接（低成本）

1. `DesignKnowledge` 对齐 Case：增加 `problem`（或明确 `insight≡problem` 文档契约）+ 可选 `strategy`  
2. `DesignKnowledge.precedent_ref: str | None`（先存 `case:ningbo_museum`）  
3. ConceptDirection：`reference_case_ids: list[str]` 与 `reference_dna` 并存一期  

### Phase B — 可写案例库（护城河开始长） ✅

4. `ArchitectureCase` 可持久（**项目级** `architecture_cases`），seeds 为 bootstrap；同 slug 项目行覆盖种子  
5. 研究确认写回：`precedent_ref` 命中种子则只链接；否则从 DesignKnowledge **创建 draft** 并回写 `precedent_ref`；`activate` 提升为检索默认可见  

### Phase C — 图从投影升级为增量边 ✅

6. 持久化确认边表 `knowledge_graph_edges`（`ConfirmedKnowledgeEdge`）  
7. Snapshot = seeds + 账本爆炸 + **确认边**（缺端点时建 stub 节点）  
8. 研究确认自动写 `INSPIRED_BY`（precedent_ref）/ `LINKED_FACT`；可 `revoke`  
9. Evidence 命名空间收敛（KN-012）✅ — `evidence_authority.py` + Presentation*/Materials* 别名；PPT 字符串契约未动  

---

## 可行动 Issue（`KN-*`）

| 编号 | 级别 | 问题 |
|------|------|------|
| KN-008 | P1 | DesignKnowledge 与 ArchitectureCase 槽位不对齐（缺 problem/strategy；无 precedent 链接） |
| KN-009 | P1 | ConceptDirection.reference_dna 无 case_id；无法回链案例库 |
| KN-010 | P1 | ArchitectureCase 仅 8 条内存 seeds，不可持久/扩展 |
| KN-011 | P2 | KnowledgeGraphSnapshot 只读时投影，无确认边持久化 |
| KN-012 | P1 | Evidence 多身份未收敛（设计 vs 汇报命名空间） |
| KN-013 | P2 | Case→DK 映射丢 design_problem 独立性（塞进 insight） |

（写入 `docs/audit/module-audit/06-parsing-knowledge.md`。）

---

## 专题衔接

| 专题 | 钩子 |
|------|------|
| 01 Domain | KnowledgeBase 仍是 Fact+Item；本专题证实「知识」≠「图」 |
| 03 推理链 | Rationale 有链无边；Research Critic 有，缺 Reasoning Artifact 身份 |
| 04 设计循环 | 批判需引用可追溯 DK/Case ID，否则 Critic 只能评散文 |
| 05 多模态 | ArchitecturalChunkType 已有 SPATIAL/MATERIAL 标签；Asset→图节点待接 |
| 06 绘画 | ResearchVisionBridge 已从 DK/Case 出视觉种子 — 知识结构直接喂绘画 |

---

## 验收（本专题）

- [x] DesignKnowledge / Case / Graph / Evidence 盘点  
- [x] 与理想 problem→…→applicability 对照  
- [x] 持久化 vs 读时投影判定  
- [x] KN-008…013 草案  
- [ ] 择优落地 Phase A（词表对齐 + precedent_ref）
- [x] Phase A 落地：`problem`/`strategy`/`precedent_ref` + `reference_case_ids`（KN-008/009/013 done）
- [x] Phase B 落地：项目级可写 `architecture_cases` + 确认研究写回建草稿（KN-010 done）
- [x] Phase C 落地：`knowledge_graph_edges` 确认边持久化 + snapshot 合并（KN-011 done）
- [x] KN-012 落地：Evidence 权威目录 + Presentation*/Materials* 命名隔离
