# P0 — Architectural Presentation Visual Quality Recovery

> **产品主线（2026-08-05）**  
> **判定**：Archium 当前是「优秀的大脑，缺少建筑师认可的视觉表达」。  
> **性质**：产品阻断项，不是 UI 优化，也不是「多加几个模板」。  
> **约束**：不新增 Agent；能力挂在既有 **Visual** / **Critic** 席位的 Service + Domain。  
> **Beta 门**：在 **VQ-008 建筑师盲评**达到门槛前，**不发布 Beta**。

**相关现行文档**

| 文档 | 关系 |
|------|------|
| [`presentation-engine-v0.3.md`](presentation-engine-v0.3.md) | 引擎能力演进线；本 P0 是其**产品优先级收束** |
| [`architectural-presentation-grammar-v1.md`](../visual/architectural-presentation-grammar-v1.md) | 语法与 VisualConcept 已有骨架；本 P0 要求**进入正式生成主链并可见** |
| [`QUALITY_GATE_STATUS.md`](../QUALITY_GATE_STATUS.md) | 诚实能力快照；RS-003 双轨仍 open |
| [`v0.2-beta-release-decision.md`](../v0.2-beta-release-decision.md) | 软件 Beta 标签决策；现增加 VQ-008 硬门 |

---

## 1. 一句话

生成「正确、规整、可读」的页面，与生成「有设计判断、视觉气质与表达张力」的建筑汇报，**不是同一个目标**。  
Archium 下一阶段产品定义从「智能建筑汇报生产工具」升级为：

> **能够理解建筑项目，并以建筑师认可的视觉语言表达项目的智能设计系统。**

---

## 2. 根因（已对照代码）

| 层 | 现状 | 缺口 |
|----|------|------|
| `LayoutPlanningService` | 「rule + optional LLM decision, deterministic geometry」 | 擅长不重叠/不溢出/安全区；不擅长主角、张力、破格、节奏 |
| `ColorSystem` | 静态 token（background / primary / accent…） | 颜色存在，但**没有页面级比例编排** |
| `TypographySystem` / `TextStyleToken` | display→source 层级 | **字号层级 ≠ 文字构图**；难表达同题多字号、空心字、巨型背景字 |
| `LayoutFamily` ×10 | 回答「这页是什么功能」 | 弱耦合审美语言；同 family 可换色仍像同一模板 |
| 候选选择 | Validity / score / 留白 / 安全偏好 | 自然偏向「最安全」，产出典型 AI PPT |
| `RenderScene` | SHAPE / CONNECTOR / FREEFORM / DECORATION 已枚举 | 需从「模型存在」升到「正式主链稳定可用」；审计 **RS-003** Scene 仍非唯一 SSOT |
| 上游概念 | `VisualConcept` / `DeckComposition` / `PacingRole` / Grammar v1 **已有** | 多数停留在规划叙述或弱偏好，**未改变最终页面气质** |

**禁止的错误解法**：每页加圆、加线、加渐变、标题加粗、加色块 → 从「普通」变成「普通且杂乱」。

需要的是 **Architectural Graphic Design Engine**，不是 Decorative Layer。

---

## 3. 目标生成链

当前大致：

```text
SlideSpec → VisualIntent → LayoutFamily → LayoutPlan → RenderScene → PPTX
```

目标：

```text
SlideSpec
  → CommunicationIntent
  → VisualConcept
  → CompositionStrategy
  → TypographyComposition
  → GraphicLanguage / GraphicMotif
  → ColorComposition
  → LayoutPlan
  → RenderScene
  → Perceptual Critic（有限修改提案）
  → Refinement
  → PPTX
```

已有模型（`VisualConcept`、`PacingRole`、Grammar）**保留并加深**，禁止平行造第二套「概念宇宙」。缺口是：**可执行构图、文字构图、色彩比例、图形母题、正式渲染、截图级 Critic、建筑师盲评**。

---

## 4. Epic 台账（GitHub 对齐）

| ID | Epic | 一句话 | 阶段 |
|----|------|--------|------|
| **VQ-001** | Semantic Typography Composition | Rich runs：多字号/字重/字距/透明度/描边/空心/旋转/纵排/巨型背景字；标题可拆分 | Phase 1 **Partial**（多字号 runs + ghost；描边/纵排 deferred） |
| **VQ-002** | Project Color Composition | 页面级色比 + Deck 色彩节奏；非「所有标题同一主色」 | Phase 2 **Partial**（BackgroundMode + accent wash/edge） |
| **VQ-003** | Architectural Graphic Motif | 项目级母题（轴网/流线/节点/剖切/引线…）从概念生长，非随机装饰 | Phase 2 **Partial**（motif → scene geometry） |
| **VQ-004** | Shape / Connector / Freeform formal rendering | 枚举能力进入正式主链；建筑标注可稳定导出 | Phase 2 **Partial**（motif→Connector/Freeform；PNG/HTML/PPTX；原生 OOXML deferred） |
| **VQ-005** | Architectural Visual Grammar Library | 先 12 种高质量语法（含变体 + Golden 截图 + 建筑师评分） | Phase 3 |
| **VQ-006** | Deck Rhythm Planner | 统一字体/网格/色板/母题；变化构图/明暗/密度；Pacing 约束防「页页一样漂亮」 | Phase 2–3 |
| **VQ-007** | Screenshot Visual Critic | PPTX→截图→多模态 Critic→**有限**修改提案→再渲染 | Phase 4 |
| **VQ-008** | Architect Blind Review Benchmark | 5 名建筑师盲测；达门槛前不发 Beta | 持续 / 门禁 |

### 12 种语法（VQ-005 首批）

1. Monumental Statement  
2. Architectural Editorial  
3. Analytical Overlay  
4. Drawing Atlas  
5. Spatial Sequence  
6. Before / Intervention / After  
7. Metric Monument  
8. Concept Collage  
9. Strategy Constellation  
10. Material Palette  
11. Timeline Ribbon  
12. Final Vision  

每种必须有：适用页、禁用条件、必备内容、视觉特征、3–5 变体、PPTX 截图 Golden、建筑师评分。

### 暂停清单（在 VQ-008 达标前）

- 更多 Agent / 协作功能扩面  
- 纯后端架构重构（非 VQ 阻塞项）  
- 更多工具台功能 / 纯 UI 美化  
- Beta 发布冲刺  

允许继续：CI 稳定性、导出正确性、Scene SSOT（RS-003）、与本 P0 直接相关的渲染深度。

---

## 5. 四阶段推进

### Phase 1 — 先让「文字会设计」（最快可见）

范围页：封面、章节页、核心理念、指标页、结尾页。  
交付：VQ-001 主链可见；两周内明显摆脱默认模板感。

### Phase 2 — 项目级色彩与图形母题

VQ-002 / VQ-003 / VQ-004 + VQ-006 初版。  
目标：一眼看出「这套 PPT 属于这个项目」。

### Phase 3 — 建筑视觉语法

VQ-005 十二种；质量优于数量。

### Phase 4 — 视觉 Critic 与候选优选

每页 3 候选（编辑式克制 / 概念性强 / 技术严谨）→ 规则 QA + 截图 Critic + 参考相似度 + Deck 重复度 → 选定。  
Critic **只读 + 有限提案**，禁止 LLM 随意重写页面。

---

## 6. 验收（VQ-008）

盲测材料：旧版 Archium / 新版 Archium / 人工优秀参考（不标来源）。

| 门槛 | 指标 |
|------|------|
| 新版对旧版胜率 | ≥ 80% |
| 「可直接使用或轻微修改」 | ≥ 60% |
| 平均视觉评分 | ≥ 7/10 |
| 人工修改时间下降 | ≥ 50% |

启发式 QA（溢出/重叠）继续保留，但**不能**再充当「好看」的定义。审美维度至少覆盖：Hierarchy、Focal Clarity、Typography Expressiveness、Color Harmony、Graphic Coherence、Composition Tension、Image Treatment、Architectural Relevance、Deck Rhythm、Template Repetition。

---

## 7. GitHub Issue 正文（创建时粘贴）

**Title:** `P0 — Architectural Presentation Visual Quality Recovery`

**Body:**

```markdown
## Summary

Archium has a strong cognitive pipeline but lacks architect-approved visual expression.
This is the sole product mainline until VQ-008 passes. No Beta until then.

Canonical doc: `docs/roadmap/architectural-visual-quality-recovery-p0.md`

## Epics

- [ ] VQ-001 Semantic Typography Composition
- [ ] VQ-002 Project Color Composition
- [ ] VQ-003 Architectural Graphic Motif
- [ ] VQ-004 Shape / Connector / Freeform formal rendering
- [ ] VQ-005 Architectural Visual Grammar Library (12 grammars)
- [ ] VQ-006 Deck Rhythm Planner
- [ ] VQ-007 Screenshot Visual Critic (bounded refinements)
- [ ] VQ-008 Architect Blind Review Benchmark (Beta gate)

## Non-goals until VQ-008

More Agents, collaboration sprawl, cosmetic UI, Beta tag.

## Acceptance (VQ-008)

- New vs old win rate ≥ 80%
- Ready / light-edit ≥ 60%
- Mean visual score ≥ 7/10
- Edit time ↓ ≥ 50%
```

---

## 8. 状态

| 项 | 值 |
|----|-----|
| 采纳日期 | 2026-08-05 |
| 状态 | **Active — sole product mainline** |
| GitHub Issue | pending（需 `gh auth login` 后创建） |
