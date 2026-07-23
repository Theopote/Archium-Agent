# Layout Families

`LayoutFamily` 描述建筑汇报常见表达结构。Registry 定义亲和内容、必需角色与变体；**坐标由 generator 确定性生成**。

## Registry

实现：`archium/infrastructure/layout/layout_family_registry.py`

| Family | 用途 | Round 1 Generator |
|--------|------|:-----------------:|
| `hero` | 主视觉开篇 / 高潮 | ✅ |
| `evidence_board` | 现场问题 / 证据网格 | ✅ |
| `drawing_focus` | 总平面 / 平面 / 剖面 | ✅ |
| `comparative_matrix` | 案例比较 / 前后对比 | ✅ |
| `process_narrative` | 过程 / 分期路径 | ✅ |
| `analytical_diagram` | 分析图 + callout | ✅ |
| `metric_dashboard` | 指标看板 | ✅ |
| `strategy_cards` | 策略卡片 | ✅ |
| `textual_argument` | 文字论述 | ✅ |
| `hybrid_canvas` | 图文混合分栏（含 `site_context` / `narrative_opening`） | ✅ |

Solver：`LayoutSolver` 已对 **全部 10 个** LayoutFamily 注册确定性 generator。`hybrid_canvas` 仍是确定性分栏，**不是** LLM 自由坐标。

## 变体示例

| Family | 变体 |
|--------|------|
| `hero` | `full_bleed` · `split` · `overlay` |
| `evidence_board` | `photo_grid` · `numbered_grid` · `journey_with_photos` |
| `drawing_focus` | `full_canvas` · `drawing_with_metrics` · … |
| `comparative_matrix` | `equal_columns` · `matrix_with_insight` · `before_after` |
| `strategy_cards` | `three_cards` · `four_cards` · `cards_with_lead` |
| `textual_argument` | `lead_and_points` · `quote_argument` · `two_column_text` |

完整列表以 Registry 源码为准。

## 生成管线

```
VisualIntent (+ ArtDirection hints)
  → candidate family/variant 决策（规则或 LLM draft）
  → LayoutGeneratorContext + content_from_slide()
  → LayoutSolver.generate(family, context)
  → LayoutPlan (elements with x/y/w/h)
  → LayoutValidationService.validate()
  → select_best by score / critical issues
```

内容映射：`content_from_slide()` 把 SlideSpec + VisualIntent 的标题、要点、指标、`hero_asset_id` 等填入 generator。

## Visual Grammar vs LayoutFamily

**Grammar**（[`visual_grammar.py`](../../archium/domain/visual/visual_grammar.py)）回答「这一页讲什么故事、要哪些证据角色」；

**Family** 回答「这些角色如何落到坐标」。

| Archetype | 强制组合（语义） | 偏好 Family |
|-----------|------------------|-------------|
| `narrative_opening` | 历史/语境照 + 矛盾 + 空间问题 + 更新目标 | `hybrid_canvas`（variant=`narrative_opening`）/ `hero` |
| `site_context_analysis` | 地图 + 交通 + 尺度 + 结论 | `hybrid_canvas` / `drawing_focus` |
| `site_problem_diagnosis` | 照片 + 编号标签 + 分析 | `evidence_board` |
| `design_strategy` | 关键词 + 概念图 + 逻辑回指问题 | `strategy_cards` / `analytical_diagram` |
| `before_after_transformation` | Before + After + 洞察 | `comparative_matrix` |

SlideSpec 写入 `page_archetype` + `required_evidence_slots`；缺槽位 → `GRAMMAR.MISSING_EVIDENCE_SLOT`。

规划上游（VG-002）：

1. `SlideIntent` / `SlideDesignBrief` 生成时识别 archetype 并写回
2. `SlideSpec` 优先继承 Brief/Intent 的 archetype，再补证据槽位
3. `apply_design_brief_to_intent` 用 Grammar 覆盖 VisualIntent 的 family / reading_order

## 图纸与照片

| 内容 | fit | crop |
|------|------|------|
| Drawing（总图/平面等） | `contain` | `forbidden` |
| Photo | 可用 `cover` | 允许安全裁切 |

校验会检查越界、重叠、文字溢出、主视觉面积、留白、图纸拉伸，以及 Asset 引用完整性：

| rule_code | 含义 | 严重度 |
|-----------|------|--------|
| `LAYOUT.MISSING_ASSET_REFERENCE` | `content_ref` 不在项目 Asset 中 / 为空 | hero → ERROR；supporting → WARNING |
| `LAYOUT.UNRESOLVED_ASSET_PATH` | Asset 存在但磁盘路径不可解析 | 同上 |
| `LAYOUT.HERO_ASSET_MISSING` | 主图素材缺失或不可加载 | ERROR |
| `LAYOUT.TECHNICAL_DRAWING_MISSING` | DRAWING 槽位无可用图纸（缺引用 / 路径失败 / 类型非 drawing·diagram / 格式不支持） | hero → ERROR；supporting → WARNING |
| `LAYOUT.UNSUPPORTED_IMAGE_FORMAT` | 路径可解析但扩展名非 png/jpg/jpeg/webp/gif | 同上 |

并产出稳定 `rule_code`。Workflow 校验会注入 `AssetReferenceContext`；PPTX adapter 对未解析素材会标记 `asset_unresolved`，渲染为明确占位而非静默空白。

## Golden Cases

| Case | Family | 路径 |
|------|--------|------|
| V1 | `drawing_focus` | `tests/golden/visual/composition/v1_drawing_focus/` |
| V2 | `evidence_board` | `tests/golden/visual/composition/v2_evidence_board/` |
| V3 | `comparative_matrix` | `tests/golden/visual/composition/v3_comparative_matrix/` |
| V4 | `analytical_diagram` | `tests/golden/visual/composition/v4_analytical_diagram/` |
| V5 | `process_narrative` | `tests/golden/visual/composition/v5_process_narrative/` |
| V6 | `metric_dashboard` | `tests/golden/visual/composition/v6_metric_dashboard/` |
| V7 | `hybrid_canvas` | `tests/golden/visual/composition/v7_hybrid_canvas/` |

每案至少包含：`layout_plan.json`、`validation_report.json`、`score_baseline.json`、`preview.png`；在 Node/pptxgen 可用时更新还会写出 `deck.pptx`。

**不能仅凭 generator 存在或 Layout Quality Score 高就认为视觉质量已通过** — golden 回归只覆盖结构/几何；完整观感需后续 Visual Critic。

```bash
pytest tests/golden/visual/composition -v
```
