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
| `hybrid_canvas` | 图文混合分栏 | ✅ |

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

## 图纸与照片

| 内容 | fit | crop |
|------|------|------|
| Drawing（总图/平面等） | `contain` | `forbidden` |
| Photo | 可用 `cover` | 允许安全裁切 |

校验会检查越界、重叠、文字溢出、主视觉面积、留白、图纸拉伸等，并产出稳定 `rule_code`。

## Golden Cases

| Case | Family | 路径 |
|------|--------|------|
| V1 | `drawing_focus` | `tests/golden/visual/composition/v1_drawing_focus/` |
| V2 | `evidence_board` | `tests/golden/visual/composition/v2_evidence_board/` |
| V3 | `comparative_matrix` | `tests/golden/visual/composition/v3_comparative_matrix/` |

```bash
pytest tests/golden/visual/composition -v
```
