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
| 视觉修辞 | **`VisualLanguageSpec`**（Typography / ColorStory / Decoration / Symbols） |
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
  → VisualLanguageSpec（字 / 色角色 / 装饰 / 符号） ← 视觉修辞
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

## 3.1 Visual Language Layer（视觉修辞核心）

高级感来自 **视觉修辞**，不是网格对齐。Gamma 调通用组件；Archium 调 **建筑视觉词汇**。

```text
VisualConcept
  └─ VisualNarrative   ← 隐喻如何「动」：geometry / direction / color_roles / components
  → VisualBudget       ← 装饰上限（防 Canva 化）
  → VisualLanguageSpec
       typography · color_story · decoration · symbols · primitive_ids
  → VisualPrimitive 目录（axis_line / flow_line / hero_statement …）
  → apply_visual_language_to_plan / scene
  → PPTX
```

| 模块 | 路径 | 职责 |
|------|------|------|
| VisualNarrative | `domain/visual/visual_narrative.py` | 完整视觉策略（非仅概念名） |
| VisualBudget | `domain/visual/visual_budget.py` | hero_ratio / lines / icons 上限 |
| Primitives | `domain/visual/primitives/` | 建筑零件目录（禁 emoji 图标包） |
| Language | `domain/visual/visual_language/` | 页级修辞聚合 |

首批高质量 Concept（加深而非堆数量）：

1. **Fragment → Network**（流线冲突）— broken_lines_to_curve · converging · gray/red/white  
2. **Existing → Transformation**（效果表达 / 改造对比）— photo + analysis line · intervention green  
3. **Layer → System**（区位与交通）— base + overlay · layered  
4. **Path → Experience**（流线优化）— path + nodes · sequential  
5. **Core → Expansion**（概念生成）— radial growth · circle mask  
6. **Quiet Argument**（结论建议）— 一句 + 留白  

### 3.2 页级视觉语法（Page Visual Grammar）

公式 = 语义槽位 + 视觉零件（不是 LayoutFamily）：

| 公式 | 语义 | 视觉零件 |
|------|------|----------|
| `problem_evidence_conflict` | Evidence + Conflict + Conclusion | photo · diagram · red_accent |
| `strategy_existing_transform` | Existing + Transformation + Future | before · arrow · after |
| `before_after_cut` | Before + Cut + After | dual image · gradient_fade |
| `process_sequence` | Sequence + Evolution + Timeline | axis · nodes · labels |
| `drawing_dominant` | Drawing + Annotation | drawing · callouts |
| `hero_statement` | Statement + Hero | giant title · thin_rule |
| `monument_image` | Monument + OneLine | full bleed · silhouette |
| `layer_analysis` | BaseMap + Overlay + Conclusion | overlay_map |
| `path_experience` | Path + Node + Sequence | flow_line · circulation |
| `core_expansion` | Core + Growth + Expansion | circle_mask · radial |
| `decision_metric` | Metric + Source | thin_rule · caption |
| `quiet_argument` | Claim + Whitespace | short statement |
| `section_opener` | SectionIndex + ShortTitle | section_index · thin_rule |
| `phasing_timeline` | Phase + Milestone | axis · nodes |
| `threshold_sequence` | Threshold + Approach + Arrival | entrance · flow |
| `evidence_triptych` | Evidence×3 + Claim | photo frames（禁三栏字墙） |
| `axonometric_callout` | Axonometric + KeyedCallout | drawing · callouts |
| `masterplan_focus` | Masterplan + NorthScale | drawing · axis |
| `program_stack` | Program + Stack + Zone | stack diagram · color |
| `quote_citation` | Quote + Attribution | short statement · caption |

实现：`domain/visual/page_visual_grammar.py` → `PageDirection.page_grammar`；Primitive 按 `visual_budget.icons` 实体化进 LayoutPlan。当前 **20 / ~20** 句型（首轮目录完成）。

### 3.3 ImageMask（图片修辞）

`ImageMaskSpec`（`circle` / `rounded` / `gradient_fade` / `silhouette`）挂在 `VisualLanguageSpec.image_mask`，写入 LayoutElement，pptxgen：圆裁（OVAL+图）、渐隐/剪影（底部半透明叠层）。

### 3.4 Atmosphere + SVG 构件

`AtmosphereSpec`（`cad_grid` / `contour` / `blueprint` / `dot_field`）挂在 `VisualLanguageSpec.atmosphere`，由页语法/隐喻选型；`apply_visual_language_to_plan` 注入 `vl_atm_*` 背景线/环/洗色（z≈0）。Contour 等描边形在 pptxgen 中按 stroke-only 渲染（不回填 surface）。

Primitive → 优先 `icon:*`（`primitive_icons.py` → 仓库内 `architectural_icons` SVG），无映射时再退到字形；`PptxGenPresentationRenderer` 在无 project 时也会解析 bundled icon 路径（Case 001 dry-run / PPTX）。

### 3.5 ImageCompositionPlan（主图 + 局部 + 分析线）

`ImageCompositionPlan` 挂在 `VisualLanguageSpec.image_composition`：

| mode | 语义 | 典型页 |
|------|------|--------|
| `photo_plus_analysis` | 主图 + conflict/flow 分析线 | 流线冲突 / 问题证据 |
| `layered_base` | 底图 + axis/boundary + 局部框 | 区位与交通 |
| `before_after` | 前后 + cut 线 | 改造对比 |
| `hero_plus_detail` | 主图 + 局部 inset 框 | 策略 / 核心生长 |
| `hero_only` | 一张大图，无分析线 | 封面 / 纪念碑 |
| `none` | 文字主导 | 结论 / 决策指标 |

`apply` 在 hero 框（或合成右半框）上注入 `vl_icp_line_*` / `vl_icp_detail_frame`，受 `VisualBudget.decorative_lines` 约束。

### 3.6 Design Corpus（结构化标注，不训练）

`DesignCorpusPage` + `DesignCorpusService`：公式范例（20×2 气质）+ Case 001 outline 20 页标注 ≥50。按 `formula_id` / `page_type` / `metaphor` 匹配，供导演与 Studio 参考。**不做**自建扩散训练。

延后：外部院优秀页截图入库、Corpus→打分权重、LLM 选型。

Case 001 dry-run：`visual_language.json`；页主张卡含 budget / narrative / grammar / mask / atmosphere / image_composition。

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

## 7. Design Corpus（已接线 v1 种子）

目标：标注优秀建筑汇报页；v1 先做**结构化元数据**（可无图），字段：

```json
{
  "page_type": "strategy",
  "visual_pattern": "diagram_first",
  "image_ratio": 0.72,
  "text_density": 0.15,
  "dominant_element": "drawing",
  "style": "minimal_architecture",
  "metaphor": null,
  "formula_id": "strategy_existing_transform"
}
```

实现：`domain/visual/design_corpus.py` + `application/visual/design_corpus_service.py`  
种子：公式范例 40 + Case 001 的 20 页 = **60 ≥50**。与 composition golden / Showcase 合流；**不做**自建扩散模型训练。

---

## 8. 与 GenSpark / Gamma 的边界

| | Gamma 类 | Archium Grammar |
|--|----------|-----------------|
| 比较页 | 两卡片 | Before/After + 空间问题 + 策略转化 |
| 数字 | 大数字卡 | 克制指标 + 来源 |
| 故事 | Hero 模板 | 页主张 + 隐喻 + 图纸/证据纪律 |
| 视觉词汇 | 通用商业组件 | **建筑视觉语言**（标题修辞 · 色叙事 · 轴/流线符号） |
| 拆页 | 通用密度 | 建筑「一页一主张」 |

---

## 9. 验收清单（v1.0）

- [x] 本文件作为现行 Grammar 索引（收敛 Expression Modes / Families / 页主张 / Preset）  
- [x] `VisualConcept` 域模型 +「流线冲突」`fragment_to_network` 切片  
- [x] Visual Language Engine v1（Typography / ColorStory / Divider）+ Case 001 封面/策略/冲突  
- [x] Visual Rhetoric Core：VisualNarrative + VisualBudget + VisualPrimitive 目录  
- [ ] Case 001 人工打开「流线冲突」页：先读到主张与隐喻，而非三卡片  
- [x] ImageMask + Atmosphere + SVG primitives（Visual Language apply → pptxgen）
- [x] ImageCompositionPlan（主图+局部+分析线）
- [x] 页语法首轮目录 ~20 句型  
- [x] Design Corpus 首批 ≥50 页标注（元数据种子；外部截图待补）  

**下一步投资优先级**：Case 001 人工视觉验收 → 外部优秀页截图入库 → 渲染打磨；**暂停**再扩 LayoutFamily / Concept 数量与新 Agent。
