# Visual Regression Baselines

Layer 1 extension on top of [Golden Case regression](../README.md): **PNG preview baselines** for the three highest-value deterministic cases.

## Scope

| Case | Scenario | Baseline path |
|------|----------|---------------|
| `case_a_hospital` | 医院老院区更新 | `baselines/case_a_hospital/` |
| `case_b_campus` | 校园建筑改造 | `baselines/case_b_campus/` |
| `case_c_competition` | 概念方案投标 | `baselines/case_c_competition/` |

Each baseline fixes:

- **Input** — regression JSON + deterministic `MockLLMProvider`
- **Theme** — Marp `default`
- **Export** — `export_marp=True`, `export_preview_images=True` (Marp `--images`)

> Marp page count includes Brief title + Storyline thesis slides, so `preview_count` may exceed `slide_count`. Visual checks use **preview PNG count**.

## What is checked (not pixel-perfect)

| Check | Detects |
|-------|---------|
| Slide / preview count | Missing or extra pages |
| Slide titles & types | Title loss, structural regressions |
| Average hash (aHash) | Large layout shifts |
| Tolerant pixel diff (≤5%) | Template / spacing drift |
| Margin ink density | Possible text or object overflow at bottom/right edges |

> For **LayoutPlan composition** golden cases (V1–V7 drawing/evidence/comparison), see [`composition/README.md`](composition/README.md) — JSON fingerprints plus **PPTX screenshot baselines** (`test_pptx_screenshot_regression.py`).

## Run

Requires Marp CLI (`npm install -g @marp-team/marp-cli`).

```bash
pytest tests/golden/visual -v -m visual_regression
```

Included in CI **marp export smoke** job.

## Update baselines (intentional visual change)

```bash
python scripts/update_visual_baselines.py
# or single case:
python scripts/update_visual_baselines.py --case case_a_hospital
```

Commit updated `baselines/<case_id>/manifest.json` and `slide_*.png` files.

## Acceptance criterion

An unintentional Marp template or renderer change should fail `test_visual_regression_matches_baseline` without manual PPT review.
