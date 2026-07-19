# Architectural Slide Visual Benchmark

真实建筑汇报页面的视觉质量基准库（**30 页**）。

## 目录结构

每个 Case 目录包含：

| 文件 | 用途 |
|------|------|
| `input.json` | 页面任务、分类、预期 LayoutFamily、素材清单 |
| `assets/` | 占位或真实输入素材 |
| `slide_spec.json` | 页面内容指纹 |
| `visual_intent.json` | 视觉意图指纹 |
| `layout_plan.json` | 版式几何指纹 |
| `validation_report.json` | 规则校验结果 |
| `deck_qa_report.json` | 单页 Deck QA 摘要 |
| `score_baseline.json` | Layout Quality 分数基线 |
| `output.pptx` | 可选 PPTX（Node 可用时生成） |
| `preview.png` | 线框预览 |
| `human_review.json` | 人工 9 维评分（手动填写；基线更新时不覆盖） |
| `layout_qa_review.json` | 可选：由 layout QA 派生的 rehearsal 分数（非人工） |
| `notes.md` | 问题与修复记录 |

## Case 目录

Case 定义集中在 `case_catalog.py`（30 条 `CaseCatalogEntry`），`case_registry.py` 负责通用构建逻辑。

| 范围 | 分类 | LayoutFamily 覆盖 |
|------|------|-------------------|
| `case_001`–`005` | A1–A5 各 1 页 | 图纸 / 照片 / 案例 / 数据 / 文字 |
| `case_006`–`008` | A2/A5 | `hero`（3 variants） |
| `case_009`–`011` | A4/A5 | `process_narrative` |
| `case_012`–`014` | A1 | `analytical_diagram` |
| `case_015`–`017` | A4/A5 | `strategy_cards` |
| `case_018`–`020` | A1/A2/A3 | `hybrid_canvas` |
| `case_021`–`022` | A1 | `drawing_focus`（补充 variant） |
| `case_023`–`024` | A2 | `evidence_board`（补充 variant） |
| `case_025`–`026` | A3 | `comparative_matrix`（补充 variant） |
| `case_027`–`028` | A4 | `metric_dashboard`（补充 variant） |
| `case_029`–`030` | A5 | `textual_argument`（补充 variant） |

每个 LayoutFamily 至少 3 个 Case；A1–A5 五类均有覆盖。

## 运行

```bash
pytest tests/benchmark/architectural_slides -v
pytest tests/benchmark/architectural_slides -v -m architectural_benchmark
```

## 更新基线

```bash
python scripts/update_architectural_benchmark_baselines.py
```

该脚本会：

1. 更新各 case 的 layout / validation / preview 等 artifact
2. **自动重新生成** `reports/benchmark-summary.json` 与 `benchmark-report.html`
3. **不会覆盖** 已有 `human_review.json`（缺失时写入占位模板）

也可使用 pytest 更新：

```bash
UPDATE_ARCHITECTURAL_BENCHMARK_BASELINES=1 pytest tests/benchmark/architectural_slides -v
```

## 报告

```bash
python scripts/build_architectural_benchmark_report.py
```

输出：`tests/benchmark/architectural_slides/reports/benchmark-report.html` 与 `benchmark-summary.json`

### CI 质量门禁（P0）

`test_benchmark_summary_report_is_current_and_consistent` 会检查：

- `benchmark-summary.json` / `benchmark-report.html` 存在
- summary 生成时间不早于各 case artifact
- `case_count` 与 30 个 case 目录一致
- 每个 case 的 `rule_passed` / `layout_score` 与 live build 及 summary 一致
- `rule_pass_rate >= 1.0`（正式 layout 规则门槛）
- **占位/派生人工评审不得 `accepted=true`**（仅 `source=manual` 可标记可交付）

当前状态：**30 页数量 + layout 规则质量已通过；人工视觉质量验收未通过**（`manual_human_accepted_count=0`，待真实 `human_review.json`）。

## 人工评分

编辑各 Case 目录下的 `human_review.json`（`source: "manual"`）。加权门槛默认 **3.5/5**（见 `HumanVisualReview.passes_threshold()`）。

使用 `UPDATE_ARCHITECTURAL_BENCHMARK_BASELINES=1` 重新生成基线时，**不会覆盖**已有 `human_review.json`；缺失时写入占位模板。layout QA 派生分数写入 `layout_qa_review.json`。

严格模式（CI 可选）拒绝占位/派生评审：

```bash
STRICT_BENCHMARK_HUMAN_REVIEW=1 pytest tests/benchmark/architectural_slides -v
```

## 与 V1–V7 Golden 的区别

- V1–V7：验证 LayoutFamily 几何与渲染回归
- Architectural Benchmark：真实建筑页面任务 + 分类体系 + 人工视觉评分 + 整套报告
