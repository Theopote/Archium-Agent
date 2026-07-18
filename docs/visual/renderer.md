# Visual Renderer

视觉编排的 PPTX 路径：**执行 LayoutPlan，不重排版式**。

## 双轨说明

| 轨 | 输入 | Node 入口 | 谁决定坐标 |
|----|------|-----------|------------|
| **LayoutPlan（视觉编排）** | `presentation.layout_instructions.json` | `render-plan.mjs` | LayoutPlan / generators |
| Legacy PresentationSpec | `presentation.spec.json` | `render.mjs` | `layouts/*.mjs` 模板 |

主汇报工作流仍可走 Legacy。视觉工作流的 `export_pptx` **只走 LayoutPlan 轨**。

## 适配层

`PptxLayoutPlanAdapter`（`layout_plan_adapter.py`）：

1. 读取 `LayoutPlan.elements`（按 `z_index`）
2. 解析 DesignSystem 字体色与 style token
3. 绑定 `SlideContentBundle.asset_paths`（`content_ref` → 文件路径）
4. 输出 `RenderedSlideInstruction` / deck JSON（`schema: archium.layout_instructions.v1`）

**不得**：改 `layout_family`、重算 `x/y/w/h`、替换为模板布局。

## 执行层

```
archium/infrastructure/renderers/pptxgen/
├── render-plan.mjs           # deck → PPTX
├── layouts/from-plan.mjs     # addText / addImage at instruction boxes
├── render.mjs                # legacy PresentationSpec
└── layouts/*.mjs             # legacy templates
```

`from-plan.mjs` 行为：

- 按指令坐标放置文本 / 图片 / 占位
- 图纸默认 `sizing: contain`；照片可用 `cover`
- 不启用 master 自动页码（页码来自 LayoutPlan 元素，若有）
- 缺失图片时画占位框，不静默跳过区域

## Python API

```python
renderer = PptxGenPresentationRenderer(settings, session=session)
deck_path, pptx_path = renderer.render_and_export_pptx_from_layout_plans(
    title=brief.title,
    plans=plans,
    design_system=design,
    output_dir=output_dir,
    slides=slides,
    project_id=project_id,
)
```

或分步：

1. `build_layout_instruction_deck(...)`
2. `export_pptx_from_layout_instructions(deck, output_dir=...)`

CLI：`PptxGenCliRunner.render_layout_instructions(deck_json, pptx_path)`。

## 产物

视觉工作流输出目录典型文件：

- `layout_instructions/slide_NN_<family>.json`
- `presentation.layout_instructions.json`
- `presentation.layout_plan.pptx`（当 `export_pptx=True`）
- `validation_reports.json`

## 依赖

与 Legacy 相同：Node.js 20+，在 `archium/infrastructure/renderers/pptxgen` 执行 `npm install`。

## 测试

```bash
pytest tests/unit/visual/test_layout_plan_pptx_export.py -q
pytest tests/smoke/test_layout_plan_pptx_render.py -q   # 真实 Node + 坐标抽检
```
