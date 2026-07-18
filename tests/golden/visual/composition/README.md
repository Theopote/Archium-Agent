# Visual Composition Golden Cases (V1–V3)

LayoutPlan JSON baselines for architectural visual composition — distinct from Marp PNG visual regression in [`../README.md`](../README.md).

## Cases

| Case | Family | Focus |
|------|--------|-------|
| `v1_drawing_focus` | `drawing_focus` | 总平面 / 图纸优先，contain + 禁裁切 |
| `v2_evidence_board` | `evidence_board` | 现场证据网格 |
| `v3_comparative_matrix` | `comparative_matrix` | 案例比较统一尺度 |

Each case directory contains:

- `layout_plan.json` — expected plan shape / family / key element roles
- `validation_report.json` — expected validation summary

## Run

```bash
pytest tests/golden/visual/composition -v
```

## Docs

See [`docs/visual/layout-families.md`](../../../docs/visual/layout-families.md).
