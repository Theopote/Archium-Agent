# Archium Presentation Engine v0.3 — 开发计划

> **定位**：Showcase Phase（展示能力阶段）。  
> **目标**：任何人第一次打开输出 PPT，都认为这是一个成熟商业产品。  
> **原则**：暂停扩展 Agent / 复杂规划 / 知识库广度；把算力与工程投入收束到 **视觉输出质量闭环**。  
> **席位约束**：不新增 Agent。本文所有「导演 / Critic / Style」能力挂在既有 **Visual** 与 **Critic** 席位的 Service + Domain 上。

**状态**：现行计划（2026-07-26）  
**前置**：[`docs/visual/README.md`](../visual/README.md)、[`docs/architecture/pipeline-roles.md`](../architecture/pipeline-roles.md)、[`docs/roadmap/visual-quality-and-editing-sprint.md`](visual-quality-and-editing-sprint.md)（历史冲刺；编辑与图片衍生基础设施可复用）

---

## 0. 阶段判断（共识）

| 维度 | 评价 | 说明 |
|------|------|------|
| 技术完成度 | ★★★★☆ | 主链与校验骨架完整 |
| 架构方向 | ★★★★★ | LLM 意图 + 确定性坐标/渲染，正确 |
| 商业展示能力 | ★★☆☆☆ | 缺事务所气质、整册震撼、杀手级 Demo |
| 用户第一印象 | ★★☆☆☆ | 「正确页面」≠「顶级所汇报」 |

**结论**：下一阶段把 **2 星展示产品 → 5 星 Demo**，而不是继续增加后台认知能力。

---

## 1. 已具备的基础（审计摘要）

主链方向正确，且已实现，**不要推倒重来**：

```text
资料 → 事实 → Brief → Storyline → SlideSpec
  → VisualIntent → LayoutPlan → 校验 → RenderScene → PPTX
```

| 能力 | 现状 | 代码/文档锚点 |
|------|------|----------------|
| DesignSystem | 单默认 `architecture-board`（16:9 / 12 栏 / 16pt 等） | `domain/visual/design_system.py` |
| LayoutFamily ×10 | 建筑汇报版式族 | `docs/visual/layout-families.md` |
| LayoutValidator + Score | 越界/重叠/字号/留白/图纸拉伸 | Layout Quality |
| ArtDirection | **全稿**视觉语言叙述（语气、策略、节奏文字） | `domain/visual/art_direction.py` |
| PageArchetype + Recipe | 开篇/区位/问题/策略/前后等语法 | `domain/visual/visual_grammar.py` |
| DeckComposition | `PacingRole` / `VisualIntensity` / 密度与版式偏好 | `domain/visual/deck_composition.py` |
| Visual Critic | `heuristic_v0` 只读几何启发式 | `domain/visual/critic.py` |
| Vision style_preset | **出图**风格（马克笔等），≠ 整册 PPT 美学 | Vision Engine |
| Golden composition | 单页/组件截图回归 | `tests/golden/visual/composition/` |

**关键区分**：今天能生成「结构正确的页面」；还不能稳定生成「某种建筑事务所审美」的整册。

---

## 2. 三个关键缺口（必须补）

### 缺口 A — 真正的视觉风格系统（Style Preset）

今天：

```text
DesignSystem（令牌） → LayoutFamily → PPTX
```

事务所汇报需要：

```text
项目气质 → Style Preset → ArtDirection 绑定 → 版式策略 + 页面节奏 → PPTX
```

**不是**再套一层「随便选个模板」；而是把 SOM / BIG / 设计院技术板等气质，编码为可执行令牌与密度策略。

### 缺口 B — 真实案例 Golden Deck（投资人看的东西）

现有 golden 验证 `layout_plan.json` / `validation_report` / `preview.png`。  
投资人看的是：**打开 PPTX 后第 1 / 5 / 10 / 20 页是否像成熟所做的汇报**。

需要 **Archium Visual Benchmark**：完整输入包 → 完整 PPTX → 人工五维评分。

### 缺口 C — 页面导演（Page Director）

今天常见路径：`SlideSpec → LayoutFamily → Generator`。  
缺的是页级创作判断：这一页只讲一个矛盾？主图占比？是否禁止三段正文？

```text
SlideSpec + PageArchetype + DeckDirective
        ↓
  PageDirector（Visual Service）
        ↓
  强化后的 VisualIntent / Brief（禁区、主矛盾、图文预算）
        ↓
  LayoutFamily + Generator
```

**不是**新 Agent；是 Visual 席位上的确定性 + 少量 LLM 结构化决策。

---

## 3. 明确暂停（本阶段禁止）

| 暂停 | 原因 |
|------|------|
| ❌ 新增 Agent / 第七席位 | 违反六席；且不提升打开 PPT 的第一印象 |
| ❌ 更复杂 Mission / 知识库广度 | 展示瓶颈不在「懂更多」，而在「看起来更专业」 |
| ❌ 大规模自建 SD 训练栈 | Vision 已有可插拔路径；本阶段优先版式与 Demo |
| ❌ 万能自由布局求解器 | 继续走 family + grammar + repair |
| ❌ 部署/安装面扩张 | 质量门未过前 deferred（仓库 hygiene） |

---

## 4. 目标产品形态

**一句话**：上传真实建筑资料包 → 一键生成可打开的专业汇报 PPTX → 前几页即可产生「这是商业产品」的判断。

**验收口号（投资人 Demo）**：

> 不要展示「AI 生成 PPT」。展示：「陕西医院改造资料包 → 一键汇报 → 30–60 秒 → 打开封面 / 基地 / 策略 / 效果页」。

---

## 5. 分阶段交付

### Phase 1 — PPT 美学核心（约 1–2 周）

#### P1.1 Style Preset 系统

**包路径（建议）**：

```text
archium/domain/visual/style/
  presets.py          # StylePreset id + 令牌覆盖
  registry.py         # 注册表
archium/application/visual/
  style_preset_service.py
```

**首批 6 个预设（产品名可微调，语义固定）**：

| Preset ID | 气质 | 密度 | 色彩倾向 | 标题 | 图面 |
|-----------|------|------|----------|------|------|
| `architecture_minimal` | SOM 式极简 | spacious | 黑白灰 | 弱/精 | 大留白、少图注 |
| `architecture_technical` | 设计院技术板 | compact | 冷灰+强调色 | 中 | 图纸密度高 |
| `architecture_luxury` | 高端竞赛/商业 | balanced | 深底或暖金克制 | 强 | 大图、少字 |
| `architecture_academic` | 高校/研究汇报 | balanced | 理性彩 | 中 | 分析图优先 |
| `architecture_urban` | 城市更新 | balanced–compact | 中性+警示点缀 | 强问题页 | 证据+总图 |
| `architecture_landscape` | 景观/环境 | spacious | 柔和自然 | 中弱 | 氛围图+剖面 |

每个 Preset 至少固化：

```json
{
  "id": "architecture_minimal",
  "typography": { "title_scale": 0.9, "body_pt": 15, "tracking": "loose" },
  "spacing": { "margin_bias": "generous", "gutter_bias": "wide" },
  "image_ratio": { "hero_min": 0.45, "drawing_fit": "contain" },
  "color": { "palette_ref": "...", "max_accent_ratio": 0.08 },
  "title_style": "quiet_bar",
  "diagram_style": "line_sparse",
  "density": "spacious",
  "forbidden": ["metric_dashboard_heavy", "icon_overload"]
}
```

**接线（必须）**：

1. `StylePreset` → 派生 / 覆盖 `DesignSystem` 令牌（不手改坐标）。  
2. `ArtDirection.design_system_id`（或新增 `style_preset_id`）绑定全稿。  
3. `DeckComposition` / Layout 候选打分读取 density / hero / forbidden。  
4. Studio / Generate UI 可选 Preset（默认 `architecture_technical` 或按项目类型推荐）。

**验收**：

- [ ] 同一 `SlideSpec` 在 `minimal` vs `technical` 下，hero 面积、字号、留白可测量差异。  
- [ ] 单测：registry 完整、非法 id 失败、绑定后 DesignSystem 哈希变化。  
- [ ] 至少 2 个 composition golden 用不同 Preset 出可对比截图。

#### P1.2 Deck 节奏控制器（强化现有模型）

**不要新建平行模型**。升级现有：

- `DeckCompositionPlan` / `SlideCompositionDirective` / `PacingRole` / `VisualIntensity`
- `SectionCompositionPlan` 高潮页标记

**新增行为**：

| 控制项 | 规则示例 |
|--------|----------|
| 高潮预算 | 20 页稿最多 2–3 个 `climax`/`hero`；相邻两页不得同为 hero |
| 密度波形 | opening spacious → evidence compact → strategy balanced → closing spacious |
| 版式重复 | 连续 ≥3 页同 LayoutFamily → Deck QA 升级为需处理 finding |
| 图片/文字比 | 由 directive 的 hero/text/drawing_priority 真正影响候选打分（非仅注释） |

**验收**：

- [ ] 医院 20 页 fixture：节奏曲线可序列化检查（无「全稿 compact」）。  
- [ ] Deck QA 对「高潮过密 / 版式三连」有稳定 rule code。

#### P1.3 Page Director（页面导演）最小切片

**服务名建议**：`PageDirectionService`（Visual）

输入：`SlideSpec` + `PageArchetype` + `SlideCompositionDirective` + `StylePreset`  
输出：结构化 `PageDirection`（写入 Brief / VisualIntent 扩展字段，**不含坐标**）：

- `single_message`：本页唯一主张（强制一句）  
- `must_show` / `must_hide`：证据槽与文字块  
- `composition_bias`：如 `photo_left | diagram_center | conclusion_bar`  
- `copy_budget`：标题/正文最大字符或块数  
- `layout_family_lock` 或强偏好  

示例：「基地交通复杂，人车混行」→ 禁止三段正文模板；偏向证据+流线+一句结论。

**验收**：

- [ ] 固定输入文本 → 可预测的 `copy_budget` 与 family 偏好（规则优先，LLM 仅填结构化字段）。  
- [ ] 与 `PageArchetype` Recipe 不冲突时合并；冲突时 Director 覆盖密度/禁区并写 evidence。

---

### Phase 2 — 建筑表达模式（约 10 个超级模板）

不是 PowerPoint「母版」。是 **表达模式** = `PageArchetype` / Recipe 的可交付强化 + 固定变体。

| # | 模式 | 视觉要求 | 映射 |
|---|------|----------|------|
| 1 | Hero Opening | 大图 + 一句概念 + 极少字 | `narrative_opening` + hero |
| 2 | Problem → Solution | 问题照 → 分析 → 策略条 | problem + strategy 跨页对 |
| 3 | Drawing Story | 总平 + 编号 + 解释 | `drawing_focus` |
| 4 | Before / After | 过去 / 未来 / 变化逻辑 | `before_after_transformation` |
| 5 | Evidence Board | 现场问题网格 + 结论条 | `evidence_board` |
| 6 | Analytical Diagram | 分析图主导、文字附属 | `analytical_diagram` |
| 7 | Strategy Cards | 3–4 策略卡，禁止堆字 | `strategy_cards` |
| 8 | Process Narrative | 分期/流程横向 | `process_narrative` |
| 9 | Metric Dashboard | 指标克制，服务决策页 | `metric_dashboard` |
| 10 | Hybrid Climax | 综合高潮页，严格容量预算 | `hybrid_canvas` + climax |

**验收**：每个模式 ≥1 个截图 golden + 人工「像不像建筑所」勾选（见 Phase 4 评分表）。

---

### Phase 3 — Visual Critic 升级（截图级）

| 层 | 现状 | v0.3 目标 |
|----|------|-----------|
| Layout Quality | 几何/规则 | 保持；继续驱动 repair |
| Visual Critic heuristic | 焦点/英雄弱等启发式 | 保留为离线快路径 |
| Visual Critic vision | 无/弱 | **截图 → 结构化 finding**（只读） |

Vision Critic 输出示例（契约）：

- 标题太弱，未形成视觉焦点  
- 主图面积不足  
- 信息密度过高 → 建议减字 30% / 主图 +20%  

**硬约束**（与现行架构一致）：

- Critic **不**静默改稿、**不**单独阻断导出（除非产品策略显式开启）。  
- 建议进入 Studio Inbox / proposal，由人接受。

**验收**：

- [ ] 对「故意做坏」的 golden 页，vision critic 命中 ≥ 约定 rule 的 80%。  
- [ ] 对通过人工审美的页，误报率可接受（记录阈值，不追求零误报）。

---

### Phase 4 — 杀手级 Demo + Visual Benchmark

#### 4.1 案例包

| Case | 主题 | 目标页数 | 气质默认 Preset |
|------|------|----------|-----------------|
| Case 001 | 医院更新汇报 | ~20 | `architecture_technical` 或 `urban` |
| Case 002 | 校园建筑改造 | ~20 | `architecture_academic` |
| Case 003 | 城市更新 | ~30 | `architecture_urban` |

每案输入：PDF / 照片 / CAD 截图 / 文本 / 规范摘录 / 指标表。  
输出：完整 `presentation.pptx`（RenderScene 主路径）。

资料与跑法放在可复现脚本下（例如 `scripts/showcase/`），**大二进制不进 git**（符合仓库 hygiene）；CI 可只跑小 fixture，完整 PPTX 作 Release / 本地 / Actions artifact。

#### 4.2 人工评分表（投资人向）

| 项 | 分 |
|----|----|
| 信息逻辑 | /10 |
| 建筑表达 | /10 |
| 美观 | /10 |
| 专业度 | /10 |
| 可修改性（Studio） | /10 |
| **合计** | **/50** |

**阶段门**：Case 001 总分 ≥ 35，且「美观」「专业度」均 ≥ 7，才宣称 Showcase 达标。

#### 4.3 Demo 脚本（对外）

1. 上传 Case 001 资料包  
2. 选择 Style Preset（或自动推荐）  
3. 「一键生成汇报」  
4. 30–60s 内可打开 PPTX（可先出关键页预览）  
5. 固定导览：封面 → 基地分析 → 设计策略 → 效果表达  

---

## 6. 优先级重排（执行序）

```text
P0  Style Preset → Deck 节奏落地 → Page Director 最小切片
P0  Visual Critic vision 切片（可与 P0 并行，但以不阻塞 Demo 为准）
P1  Case 001 完整 Demo（医院）+ 人工评分
P1  10 表达模式 golden
P2  Case 002 / 003
P2  Vision 概念图/分析图增强（服务 Demo 缺图页，不单独开 Agent）
```

与旧冲刺关系：

- Studio 编辑 V1、ImageDerivative、截图回归：**保留并服务 Showcase**。  
- Layout Grammar 变体扩展：并入 Phase 2 表达模式。  
- Vision Intelligence 大规模能力：降为 P2，仅补 Demo 缺图。

---

## 7. 架构接线（一张图）

```text
StylePreset ──► DesignSystem 令牌
       │
ArtDirection ──► 全稿气质 + pacing_strategy
       │
DeckCompositionPlan ──► 页级 PacingRole / Intensity / Density
       │
PageDirector ──► PageDirection（单主张、禁区、图文预算）
       │
VisualIntent + LayoutFamily Generator ──► LayoutPlan（坐标）
       │
Validate / Capacity / Repair
       │
RenderScene → PPTX
       │
Layout Quality + Visual Critic (heuristic + vision) ──► 只读 findings
```

LLM：**内容理解、叙事、结构化意图、可选导演字段、可选视觉审查**。  
确定性系统：**坐标、网格、渲染、几何校验、节奏硬约束**。

---

## 8. Cursor / Codex 开发 Prompt（可直接复制）

### Prompt A — Style Preset

```text
Implement Architecture Style Preset system for Archium Presentation Engine v0.3.

Constraints:
- No new Agent classes. Visual seat only (domain + application service).
- Reuse DesignSystem / ArtDirection; do not invent a second coordinate system.
- Add archium/domain/visual/style/ with 6 presets: architecture_minimal,
  architecture_technical, architecture_luxury, architecture_academic,
  architecture_urban, architecture_landscape.
- Each preset must produce measurable DesignSystem token overrides
  (typography, spacing, color, density, image hero ratio, forbidden styles).
- Wire preset selection into ArtDirection (or style_preset_id) and layout
  candidate scoring via DeckComposition directives.
- Add unit tests + 2 composition golden screenshots comparing minimal vs technical.
- Follow docs/roadmap/presentation-engine-v0.3.md Phase 1.1.
- Do not expand knowledge base or add agents.
```

### Prompt B — Deck Rhythm + Page Director

```text
Strengthen DeckCompositionPlan execution and add PageDirectionService.

Constraints:
- Extend existing domain/visual/deck_composition.py; no parallel rhythm model.
- Enforce climax budget, density waveform, and LayoutFamily streak rules in Deck QA.
- PageDirectionService (Visual) outputs structured PageDirection without coordinates:
  single_message, must_show/must_hide, composition_bias, copy_budget, family preference.
- Merge with PageArchetype recipes; on conflict, Director wins on density/forbidden and records evidence.
- Prefer deterministic rules; LLM only fills structured fields when enabled.
- Tests: hospital 20-slide fixture rhythm curve; fixed copy → predictable copy_budget.
- See docs/roadmap/presentation-engine-v0.3.md Phase 1.2–1.3.
```

### Prompt C — Vision Visual Critic

```text
Upgrade Visual Critic with optional screenshot vision path; keep heuristic_v0.

Constraints:
- Critic remains read-only: no silent auto-repair, no sole export block.
- Input: page screenshot (+ optional LayoutPlan metrics). Output: VisualCriticFinding list
  with rule codes and actionable suggestions (e.g. reduce copy 30%, increase hero 20%).
- Reuse domain/visual/critic.py models; add application service path behind settings flag.
- Add adversarial golden pages that must trigger findings; document false-positive budget.
- Six seats only; Critic seat services, not CriticAgent2.
- See docs/roadmap/presentation-engine-v0.3.md Phase 3.
```

### Prompt D — Showcase Case 001

```text
Build Archium Showcase Case 001: hospital renovation deck (~20 pages).

Constraints:
- Input pack under scripts/showcase/case_001_hospital/ (manifest + small fixtures in repo;
  large binaries gitignored / Actions artifacts only).
- Pipeline: materials → … → RenderScene → presentation.pptx (no legacy Spec fallback).
- Default style_preset architecture_technical or architecture_urban.
- Produce scoring checklist matching docs/roadmap/presentation-engine-v0.3.md §4.2.
- Demo script: cover, site analysis, strategy, atmosphere pages must be openable.
- No new agents; reuse hospital-renovation-report skill checklists where applicable.
```

---

## 9. 周计划建议（压缩版）

| 周 | 焦点 | 退出标准 |
|----|------|----------|
| W1 | Style Preset + DesignSystem 接线 + UI 选择 | 两预设可对比截图 |
| W1–W2 | Deck 节奏硬约束 + Page Director MVP | 节奏测试绿；导演字段进 Intent |
| W2 | 表达模式 1–5 golden + Critic vision 旗标 | 5 模式可演示 |
| W3 | Case 001 端到端 + 人工评分 | 总分 ≥35 或列缺陷清单 |
| W4 | 表达模式 6–10 + Demo 排练 + 修 Critic 误报 | 可对外投屏 |

---

## 10. 成功定义（一句话）

当非工程师打开 Case 001 的 PPTX，在 **10 秒内**说出「这像设计院做的」而不是「这像 AI 套模板」——v0.3 Showcase 阶段达标。

---

## 11. 文档与实现同步

| 变更落地时 | 同步更新 |
|------------|----------|
| Style Preset | `docs/visual/design-system.md`、本计划勾选 |
| Deck / Director | `docs/visual/architecture.md`、`DECK_COMPOSITION_ARCHITECTURE.md`（行为为准，可删过时分析） |
| Critic vision | `docs/visual/README.md` Critic 段 |
| Case 001 | `tests/golden/` 或 `scripts/showcase/` README + 评分表 |

本文件是 **现行 Showcase 计划**；与意图驱动 P0–P3（`current-system.md`）并行不冲突——后者偏认知闭环，本文件偏 **打开 PPT 的第一印象**。
