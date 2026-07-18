# Visual QA Calibration Sprint

目标：验证现有 Pillow 启发式规则是否**真正帮助建筑师**，而不是制造噪声。

**本阶段不新增检测器。** 只做标注、跑分、调阈值、更新正式/疑似策略。

## 语料目标

| 类别 | 数量 |
|------|------|
| 总平面图 (`site_plan`) | 50 |
| 平面图 (`floor_plan`) | 50 |
| 剖面图 (`section`) | 30 |
| 立面图 (`elevation`) | 30 |
| 分析图 (`diagram`) | 50 |
| 效果图/现场照片 (`photo`) | 50 |

**合计 260 张。**

## 标注字段

每张图在 `corpus/manifest.json` 的 `samples[]` 中增加一条记录：

```json
{
  "id": "site_plan_001",
  "path": "images/site_plan_001.png",
  "category": "site_plan",
  "labels": {
    "drawing_type": "site_plan",
    "has_north_arrow": true,
    "has_legend": false,
    "is_low_resolution": false,
    "is_clipped": false,
    "excessive_margins": false,
    "high_text_density": false,
    "low_contrast": false
  },
  "notes": "含图框与标题栏，边距大但属正常"
}
```

- 不确定的字段设为 `null`，该检查项不计入分母。
- 图片放在 `corpus/images/`，路径相对于 `manifest.json`。
- 大图可不提交 git，本地路径一致即可；CI 可选跑 calibration（`pytest -m calibration`）。

## Precision 目标

| 检查项 | Rule code | Precision 目标 |
|--------|-----------|----------------|
| 文件损坏/不存在 | `VISUAL.ASSET_*` | ≥ 99% |
| 低分辨率 | `VISUAL.DIMENSIONS_TOO_SMALL` | ≥ 95% |
| 图纸类型 | `VISUAL.DRAWING_TYPE_MISMATCH` | ≥ 85% (top-1 accuracy) |
| 指北针 | `VISUAL.MISSING_NORTH_ARROW` | ≥ 85% |
| 图例 | `VISUAL.MISSING_LEGEND` | ≥ 80% |
| 裁切 | `VISUAL.CONTENT_CLIPPED` | ≥ 75% |
| 文字密度 | `VISUAL.HIGH_TEXT_DENSITY` | ≥ 75% |

## 运行校准

```bash
# 安装完整依赖（含 Pillow）
pip install -e ".[full,dev]"

# 生成报告 → tests/calibration/visual_qa/corpus/calibration_report.json
python scripts/calibrate_visual_qa.py

# 或指定 manifest
python scripts/calibrate_visual_qa.py --manifest tests/calibration/visual_qa/corpus/manifest.json
```

报告包含每项的 precision / recall / FPR / FNR，以及是否 `meets_target`。

## 策略联动

- `calibration_report.json` 中 **`meets_target: true`** 的规则，才可在高置信度下发出**正式**问题。
- **未达标**规则：即使 confidence ≥ 0.85，也仅显示为 **【疑似】**（`requires_confirmation=true`），**不阻断导出**。
- 资产加载失败（`VISUAL.ASSET_*`）始终为正式问题；必需素材失败仍可阻断导出。

修改阈值或 analyzer 逻辑后：

1.  bump `ANALYZER_VERSION`
2.  重新跑校准脚本
3.  提交更新后的 `calibration_report.json`（语料达标后）

## 测试

```bash
pytest tests/calibration/visual_qa -m calibration -v
pytest tests/unit/test_visual_qa_calibration.py -v
```

## 标注建议

- **留白过大**：图框、标题栏、规范留白不算问题；仅当有效图面占比明显偏低时标 `excessive_margins: true`。
- **裁切**：图框线、深色边框不算裁切；仅当建筑内容被截断时标 `is_clipped: true`。
- **文字过密**：复杂线稿/树阵/等高线不算；标注意图可读性是否受影响。
- **指北针/图例**：标实际可见性，而非规范要求（总平面不一定都有图例）。
