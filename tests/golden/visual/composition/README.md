# Visual Composition Golden Cases

Two **separate** visual regression tracks — do not conflate them.

| Track | Marker | Pipeline | Artifact |
|-------|--------|----------|----------|
| **preview_visual_regression** | `preview_visual_regression` | LayoutPlan → Python wireframe | `preview.png` + JSON |
| **pptx_visual_regression** | `pptx_visual_regression` | LayoutPlan → PptxGenJS → PPTX → LibreOffice/PowerPoint | `pptx_screenshot.png` |

Python PNG / CairoSVG preview validates **geometry boxes**. Final delivery must pass **PPTX screenshot** regression.

## Cases

| Case | Family | Focus | CI pptx baseline |
|------|--------|-------|------------------|
| `v1_drawing_focus` … `v7_hybrid_canvas` | various | Layout families | yes |
| `v8_process_narrative_icons` | `process_narrative` | 语义图标箭头 | yes |
| `v9_metric_dashboard_icons` | `metric_dashboard` | 指标装饰图标 | yes |
| `v10` … `v18` | icon expansion | 长标题 / 深浅主题 / 小尺寸 / stroke 待定 / 4:3 / 缺失与非法 ref / 8 步密集 | builders + unit tests; promote via approve |

## PPTX screenshot update (human review required)

```text
generate candidates → CI artifact / local review → approve-baseline → commit
```

```bash
# 1) Candidates only (never touches committed baselines)
python scripts/update_layout_pptx_screenshot_baselines.py --case v8_process_narrative_icons
# or expansion:
python scripts/update_layout_pptx_screenshot_baselines.py --include-expansion

# 2) Review candidates under tests/golden/visual/composition/<id>/candidates/

# 3) Approve explicitly (requires --i-reviewed; no --all)
python scripts/approve_layout_pptx_screenshot_baselines.py --case v8_process_narrative_icons --i-reviewed
```

Forbidden: after a red CI run, bulk-overwrite all baselines and push without review.

Pytest with `ARCHIUM_WRITE_PPTX_SCREENSHOT_CANDIDATES=1` (or legacy `UPDATE_LAYOUT_PPTX_SCREENSHOT_GOLDENS=1`) also writes **candidates only**.

## Run

```bash
# Preview / JSON geometry
pytest tests/golden/visual/composition/test_golden_cases.py -m preview_visual_regression -v

# Final PPTX screenshots (needs Node + LibreOffice + pdftoppm)
pytest tests/golden/visual/composition/test_pptx_screenshot_regression.py -m pptx_visual_regression -v
```

CI job **layout pptx screenshot regression** runs both tracks; on failure uploads `candidates/**` as artifacts for approve-baseline.
