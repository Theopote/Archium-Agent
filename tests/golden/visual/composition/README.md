# Visual Composition Golden Cases (V1–V9)

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
| `v8_process_narrative_icons` | `process_narrative` | 4 阶段 + 语义图标箭头 + 阶段图示 + 总结 |
| `v9_metric_dashboard_icons` | `metric_dashboard` | 4 指标 + 语义图标 + 趋势图 + 结论 |

Each case directory contains:

| Artifact | Purpose |
|----------|---------|
| `layout_plan.json` | family / variant / element geometry fingerprint |
| `validation_report.json` | valid / **Layout Quality** score / rule codes |
| `score_baseline.json` | Layout Quality score baseline（非 Visual Quality） |
| `preview.png` | deterministic wireframe preview of boxes |
| `deck.pptx` | optional real PPTX (generated when Node/pptxgen available at update time) |
| `pptx_screenshot.png` | rasterized first slide from `deck.pptx` (LibreOffice + pdftoppm) |
| `pptx_screenshot_manifest.json` | screenshot dimensions + average hash for regression |

Volatile UUIDs and timestamps are stripped so CI can catch layout regressions.
**Generator existence alone is not a visual-quality pass** — JSON goldens gate geometry; **PPTX screenshot baselines** gate rendered appearance (catches “data-valid but visually awkward” drift).

## LayoutPlan PPTX screenshot regression

Re-renders each case via PptxGenJS, rasterizes slide 1 with [`pptx_screenshot.py`](../../../archium/infrastructure/renderers/pptx_screenshot.py), and compares to committed PNG baselines (same tolerant checks as Marp visual regression: aHash, ≤5% pixel diff, margin ink).

Requires **Node.js**, **PptxGenJS** (`npm ci` in `archium/infrastructure/renderers/pptxgen`), and a rasterizer:

- **Linux / CI:** LibreOffice + `pdftoppm` (Poppler)
- **Windows:** Microsoft PowerPoint COM (fallback when LibreOffice is absent)

```bash
pytest tests/golden/visual/composition/test_pptx_screenshot_regression.py -v -m layout_pptx_screenshot
```

Included in CI job **layout pptx screenshot regression** (Ubuntu + `libreoffice` + `poppler-utils`). Missing committed baselines fail the job — CI does **not** auto-bootstrap.

Prefer regenerating baselines on **Linux** so they match CI LiberOffice output; Windows PowerPoint baselines may need a one-time Linux refresh if aHash/pixel tolerance fails in CI.

### Update screenshot baselines (intentional renderer / theme change)

```bash
# Windows PowerShell
$env:UPDATE_LAYOUT_PPTX_SCREENSHOT_GOLDENS="1"
py -c "from scripts.update_layout_pptx_screenshot_baselines import main; raise SystemExit(main())"
Remove-Item Env:UPDATE_LAYOUT_PPTX_SCREENSHOT_GOLDENS
```

```bash
# macOS / Linux / CI
UPDATE_LAYOUT_PPTX_SCREENSHOT_GOLDENS=1 python scripts/update_layout_pptx_screenshot_baselines.py
```

Commit `pptx_screenshot.png` and `pptx_screenshot_manifest.json` under each `v*/` directory.

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
