# Archium Architectural Presentation Grammar v1.0

> **定位**：建筑汇报的「表达语法」——什么内容应该长什么样。  
> **不是**：PowerPoint 母版、Gamma 卡片库、或新 Agent。  
> **席位**：全部挂在既有 **Visual** + **Critic** 服务上。  
> **状态**：v1.0（2026-07-27）— 收敛现有实现，补 VisualConcept 页级隐喻切片。

**相关实现**：

| 层 | 锚点 |
|----|------|
| 整册气质 | StylePreset + `presentation_personality` / `content_policy` |
| 整册节奏 | DeckComposition / PacingRole / VisualIntensity |
| 页主张 | `PageDirection`（产品名）/`claim` · `emotion` · `evidence_priority` · `avoid` |
| 页隐喻 | **`VisualConcept`**（本版新增；≠ Vision 出图 Brief） |
| 表达模式 | Expression Modes ×10 |
| 版式族 | LayoutFamily ×10 + generators |
| 只读审查 | Visual Critic `screenshot_v1` / `vision_v1` |

---

## 1. 一句话

Gamma 做漂亮通用 PPT；Archium 要做 **像有经验的建筑设计总监一样组织汇报**：先主张与隐喻，再证据与图纸，最后才是坐标。

```text
资料 / 事实
  → SlideSpec（讲什么）
  → PageDirection 页主张（claim / emotion / evidence / avoid）
  → VisualConcept（视觉隐喻 · 色故事 · 图面语言）   ← 美学关键步
  → Expression Mode + LayoutFamily（结构）
  → LayoutPlan → RenderScene → PPTX
  → Critic（只读）
```

**禁止**：内容直接跳到「左图右文三卡片」而不经过主张与隐喻。

---

## 2. 页类型（Page Kinds）与默认表达

| 页类型（产品） | Emotion | 默认 Expression Mode | 默认 Family | 图面占比目标 | 文字密度 |
|----------------|---------|----------------------|-------------|--------------|----------|
| 封面 / 愿景 | climax | `hero_opening` | `hero` full_bleed | 图 ≥ 65% | 极低（一句） |
| 区位 / 总图 | calm | `drawing_story` | `drawing_focus` | **图纸 ≥ 70–85%** | 标注为主 |
| 问题 / 证据 | problem | `evidence_board` | `evidence_board` | 证据图 ≥ 50% | 短结论条 |
| 流线冲突（医院） | problem | + VisualConcept `fragment_to_network` | evidence / diagram | 图+示意 ≥ 55% | ≤1 要点 |
| 策略 | strategy | `strategy_cards`（建筑语境慎用卡片墙） | strategy / diagram | 中 | 3–4 短卡 |
| 前后对比 | strategy | `before_after` | `comparative_matrix` | 双图主导 | 一句洞察 |
| 分析图 | calm | `analytical_diagram` | `analytical_diagram` | diagram 主导 | callout |
| 高潮 / 氛围 | climax | `hybrid_climax` / hero | hero / hybrid | 大图 | 一句 |
| 指标 / 决策 | decision | `metric_dashboard` | metric（克制） | 低–中 | 数字优先 |
| 分期 | strategy | `process_narrative` | process | 中 | 步骤短标 |

建筑特有构图（语法名 → 现有实现）：

| 语法名（产品） | 现有 Family / Mode | 规则摘要 |
|----------------|-------------------|----------|
| Monument Image | `hero` / `full_bleed` | 一张大图 + 一句；禁要点墙 |
| Drawing Dominant | `drawing_focus` | 图纸 ≥70%；文字为编号注解 |
| Diagram Narrative | `analytical_diagram` / `process_narrative` | 关系 / 路径 / 转化，非卡片 |
| Spatial Sequence | `process_narrative` | 入口→庭院→大厅… |
| Layered Analysis | `drawing_focus` + annotations / hybrid | 底图 + 分析层 + 结论层 |

`strategy_cards` / `metric_dashboard` 允许，但 **Technical / Minimal Preset 软降权**；竞赛气质页优先 Diagram / Drawing / Hero。

---

## 3. VisualConcept（页级视觉隐喻）

与 Vision 管线的 `VisualConceptBrief`（出图提示）**分轨**：本模型只服务 **汇报页构图叙事**。

```json
{
  "concept_name": "Broken Flow → Connected Campus",
  "visual_metaphor": "fragment_to_network",
  "color_story": ["gray", "red", "white"],
  "graphic_language": "architectural_diagram",
  "image_strategy": "contrast_before_after",
  "drawing_min_area_ratio": 0.45,
  "whitespace_hint": 0.22
}
```

| 字段 | 含义 |
|------|------|
| `concept_name` | 人话概念名（可上封面条） |
| `visual_metaphor` | 可执行隐喻 id（如 fragment_to_network） |
| `color_story` | 有序色叙事（非完整色板） |
| `graphic_language` | diagram / photo_evidence / drawing_board… |
| `image_strategy` | 图如何叙事（非滤镜参数） |
| `drawing_min_area_ratio` | 主图/图纸面积下限（布局偏好） |
| `whitespace_hint` | 目标留白提示（与 Preset content_policy 取更严） |

**最小切片（已实现）**：医院 Case 001「流线冲突」→ 强制 `fragment_to_network`（灰/警示红/白 · 图示优先 · 禁长文）。

---

## 4. 页主张契约（Page Claim）

建筑师输入语义（产品）：

1. **claim** — 这一页只讲一句  
2. **emotion** — problem / strategy / climax / calm / decision  
3. **evidence_priority** — 有序证据（越前越优先）  
4. **avoid** — 禁止项（长文、通用 icon、三栏字墙…）

导演派生（非建筑师输入）：

- `composition_bias`（photo_left 等）  
- LayoutFamily / variant  
- CopyBudget（与 StylePreset `content_policy` **取更严者**）

产物：`page_claims.json`（Showcase Case 001 dry-run）。

---

## 5. 内容密度与拆页（Grammar 规则）

触发「建议拆页」（接入既有 SplitProposal / Critic，逐步硬化）：

| 信号 | 阈值（v1 约定） |
|------|-----------------|
| 正文过长 | message 超 Preset/`CopyBudget` |
| 要点过多 | key_points > budget |
| 概念数过多 | 同页 ≥3 个互不从属设计概念 |
| 图面不足 | 主视觉面积 < VisualConcept/`drawing_min` 或 Preset 留白目标冲突 |

建筑原则：**一页一主张**；三概念必须拆成 A 背景 / B 问题 / C 策略。

---

## 6. StylePreset × Grammar

| Preset | Personality（摘要） | Grammar 偏向 |
|--------|---------------------|--------------|
| technical | evidence_first · low · supporting | Drawing / Evidence / Diagram |
| minimal | argument_first · low · dominant | Monument / 大留白 · 少卡 |
| luxury | experience_first · high · dominant | Hero / 少字 · 高留白 |
| academic | analysis_first · low · equal | Diagram / Process |
| urban | evidence_first · medium · equal | Evidence + Masterplan |
| landscape | experience_first · medium · dominant | Atmosphere + Section |

---

## 7. Design Corpus（下一阶段，不训练）

目标：标注 100–200 页优秀建筑汇报（SOM / Foster / 国内优秀院…），字段示例：

```json
{
  "page_type": "strategy",
  "visual_pattern": "diagram_first",
  "image_ratio": 0.72,
  "text_density": 0.15,
  "dominant_element": "drawing",
  "style": "minimal_architecture",
  "metaphor": null
}
```

先做结构化语料与匹配，**不做**自建扩散模型训练。与 Case 001 / composition golden 合流。

---

## 8. 与 GenSpark / Gamma 的边界

| | Gamma 类 | Archium Grammar |
|--|----------|-----------------|
| 比较页 | 两卡片 | Before/After + 空间问题 + 策略转化 |
| 数字 | 大数字卡 | 克制指标 + 来源 |
| 故事 | Hero 模板 | 页主张 + 隐喻 + 图纸/证据纪律 |
| 拆页 | 通用密度 | 建筑「一页一主张」 |

---

## 9. 验收清单（v1.0）

- [x] 本文件作为现行 Grammar 索引（收敛 Expression Modes / Families / 页主张 / Preset）  
- [x] `VisualConcept` 域模型 +「流线冲突」`fragment_to_network` 切片  
- [ ] Case 001 人工打开「流线冲突」页：先读到主张与隐喻，而非三卡片  
- [ ] ImageCompositionPlan（主图+局部+分析线）— v0.3 后 / Visual Intelligence  
- [ ] Design Corpus 首批 ≥50 页标注  

**下一步投资优先级**：Grammar 约束落地页（本切片）→ Image Composition → Corpus；**暂停**再扩 StylePreset 数量与新 Agent。
