# Visual Composition Golden Cases (V1–V7)

LayoutPlan JSON baselines for architectural visual composition — distinct from Marp PNG visual regression in [`../README.md`](../README.md).

## Cases

| Case | Family | Focus |
|------|--------|-------|
| `v1_drawing_focus` | `drawing_focus` | 总平面 / 图纸优先，contain + 禁裁切 |
| `v2_evidence_board` | `evidence_board` | 现场证据网格 |
| `v3_comparative_matrix` | `comparative_matrix` | 案例比较统一尺度 |
| `v4_analytical_diagram` | `analytical_diagram` | 流线分析图 + 图例 + 三条结论 + 来源 |
| `v5_process_narrative` | `process_narrative` | 4 阶段 + 箭头 + 阶段图示 + 总结 |
| `v6_metric_dashboard` | `metric_dashboard` | 5 指标 + 趋势图 + 结论 |
| `v7_hybrid_canvas` | `hybrid_canvas` | 主图纸 + 辅助图 + 指标 + 文字 + 图注 |

Each case directory contains:

| Artifact | Purpose |
|----------|---------|
| `layout_plan.json` | family / variant / element geometry fingerprint |
| `validation_report.json` | valid / score / rule codes |
| `score_baseline.json` | score baseline for regression |
| `preview.png` | deterministic wireframe preview of boxes |
| `deck.pptx` | optional real PPTX (generated when Node/pptxgen available at update time) |

Volatile UUIDs and timestamps are stripped so CI can catch layout regressions.
**Generator existence alone is not a visual-quality pass** — these goldens are the regression gate.

## Update baselines (intentional geometry change)

```bash
# Windows PowerShell
$env:UPDATE_VISUAL_COMPOSITION_GOLDENS="1"
pytest tests/golden/visual/composition -v
Remove-Item Env:UPDATE_VISUAL_COMPOSITION_GOLDENS
```

```bash
# macOS / Linux
UPDATE_VISUAL_COMPOSITION_GOLDENS=1 pytest tests/golden/visual/composition -v
```

## Run

```bash
pytest tests/golden/visual/composition -v
```

## Docs

See [`docs/visual/layout-families.md`](../../../docs/visual/layout-families.md).
