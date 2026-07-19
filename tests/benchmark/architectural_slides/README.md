# Architectural Slide Visual Benchmark

真实建筑汇报页面的视觉质量基准库（第一阶段：5 个示例 Case，目标扩展至 30 页）。

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
| `human_review.json` | 人工 9 维评分模板 |
| `notes.md` | 问题与修复记录 |

## 当前 Case（5/30）

| Case | 分类 | 页面类型 | LayoutFamily |
|------|------|----------|--------------|
| `case_001_site_plan` | A1 图纸 | 单张总平面主导页 | `drawing_focus` |
| `case_002_site_photos` | A2 照片 | 四张现场问题照片 | `evidence_board` |
| `case_003_case_comparison` | A3 案例 | 三案例横向比较 | `comparative_matrix` |
| `case_004_economic_metrics` | A4 数据 | 经济技术指标 | `metric_dashboard` |
| `case_005_design_concept` | A5 文字 | 设计理念 | `textual_argument` |

## 运行

```bash
pytest tests/benchmark/architectural_slides -v
pytest tests/benchmark/architectural_slides -v -m architectural_benchmark
```

## 更新基线

```bash
UPDATE_ARCHITECTURAL_BENCHMARK_BASELINES=1 pytest tests/benchmark/architectural_slides -v
python scripts/update_architectural_benchmark_baselines.py
```

## 报告

```bash
python scripts/render_architectural_benchmark.py
python scripts/build_architectural_benchmark_report.py
```

输出：`tests/benchmark/architectural_slides/reports/benchmark-report.html` 与 `benchmark-summary.json`

## 人工评分

编辑各 Case 目录下的 `human_review.json`。加权门槛默认 **3.5/5**（见 `HumanVisualReview.passes_threshold()`）。

## 与 V1–V7 Golden 的区别

- V1–V7：验证 LayoutFamily 几何与渲染回归
- Architectural Benchmark：真实建筑页面任务 + 分类体系 + 人工视觉评分 + 整套报告
