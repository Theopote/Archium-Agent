# 建筑表达模式（Expression Modes）

v0.3 Phase 2：**不是** PowerPoint 母版，而是可锁定版式族 + 变体 + 字数预算 + 构图偏向的建筑汇报表达模式。

## 位置

- Domain：`archium/domain/visual/expression_mode.py`
- 由 `PageDirectionService` 识别并写入 `PageDirection.expression_mode_id` / `locked_layout_variant`
- `VisualIntent.expression_mode_id` + `preferred_layout_variant` 影响布局候选变体排序

## 十种模式

| ID | 名称 | 主族 / 变体 | 要点 |
|----|------|-------------|------|
| `hero_opening` | Hero Opening | `hero` / `full_bleed` | 大图 + 一句概念 |
| `problem_to_solution` | Problem → Solution | `evidence_board` / `diagnosis_split` | 问题半页（配对策略页） |
| `drawing_story` | Drawing Story | `drawing_focus` / `drawing_with_annotations` | 图纸 + 编号 |
| `before_after` | Before / After | `comparative_matrix` / `before_after` | 前后对照 |
| `evidence_board` | Evidence Board | `evidence_board` / `numbered_grid` | 证据网格 + 结论条 |
| `analytical_diagram` | Analytical Diagram | `analytical_diagram` / `diagram_with_callouts` | 分析图主导 |
| `strategy_cards` | Strategy Cards | `strategy_cards` / `strategy_concept` | 3–4 策略卡 |
| `process_narrative` | Process Narrative | `process_narrative` / `steps_horizontal` | 分期横向 |
| `metric_dashboard` | Metric Dashboard | `metric_dashboard` / `metric_cards` | 克制指标 |
| `hybrid_climax` | Hybrid Climax | `hybrid_canvas` / `freeform` | 高潮页减负 |

每个模式含 `human_checklist`（人工「像不像建筑所」勾选项），供 Showcase / 投资人 Demo 评分。

## 与 PageArchetype 的关系

| PageArchetype | 默认 Expression Mode |
|---------------|----------------------|
| `narrative_opening` | `hero_opening` |
| `site_context_analysis` | `drawing_story` |
| `site_problem_diagnosis` | `evidence_board` |
| `design_strategy` | `strategy_cards` |
| `before_after_transformation` | `before_after` |

文本信号可覆盖默认映射（例如标题含「分期」→ `process_narrative`）。

## 验证

```bash
pytest tests/unit/visual/test_expression_modes.py -q
```

既有 composition golden（V1–V7、V19–V23）继续覆盖对应版式结构；Expression Mode 负责**选择与锁定**，不另起坐标系统。

完整建筑汇报语法（页主张 → VisualConcept → Family 比例）：见 [Architectural Presentation Grammar v1.0](architectural-presentation-grammar-v1.md)。
