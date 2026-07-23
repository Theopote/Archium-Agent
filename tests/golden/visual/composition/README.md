# Visual Composition Golden Cases

Two **separate** visual regression tracks — do not conflate them.

| Track | Marker | Pipeline | Artifact |
|-------|--------|----------|----------|
| **preview_visual_regression** | `preview_visual_regression` | LayoutPlan → Python wireframe | `preview.png` + JSON |
| **pptx_visual_regression** | `pptx_visual_regression` | LayoutPlan → PptxGenJS → PPTX → LibreOffice/PowerPoint | `pptx_screenshot.png` |

Python PNG / CairoSVG preview validates **geometry boxes**. Final delivery must pass **PPTX screenshot** regression.

## Font binding

PPTX screenshot manifests include ``font_manifest_hash`` (Pillow FreeType file
hashes for Microsoft YaHei + Arial regular/bold, with Noto/Liberation fallbacks
on Linux). Same-platform hash drift fails as **font drift**, not a silent pixel
diff. Approve baselines on the **CI platform (Linux)** so ``font_platform=linux``
locks the CI font set.

## Cases

| Case | Family | Focus | CI pptx baseline |
|------|--------|-------|------------------|
| `v1_drawing_focus` … `v7_hybrid_canvas` | various | Layout families | yes |
| `v19_site_context_analysis` … `v22_before_after_transformation` | grammar archetypes | 区位 / 现状问题 / 设计策略 / 改造前后 | preview JSON only (promote later) |
| `v8_process_narrative_icons` | `process_narrative` | 语义图标箭头 | yes |
| `v9_metric_dashboard_icons` | `metric_dashboard` | 指标装饰图标 | yes |
| `v14_icons_stroke_recolor` | `metric_dashboard` | accent 主题描边 recolor | yes |
| `v10`–`v13`, `v15`–`v18` | icon expansion | 长标题 / 深浅主题 / 小尺寸 / 4:3 / 缺失与非法 ref / 8 步密集 | builders + unit tests; promote via approve |

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
