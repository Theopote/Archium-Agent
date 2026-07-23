**Batch 11（Rendering / PPTX）完成。**

### 已修
1. **导出前解析 URI**：`PptxRenderer` 调用 `AssetPathResolver.resolve_scene`（Studio / workflow / recovery 传入 `project_id`）
2. **Adapter 防御**：`storage://` / `project://` / `benchmark://` 不会再传给 Node；优先 `resolved_path`
3. **Chart 预览一并解析**；静默跳过改为 `scene_pptx_unavailable_reason` + workflow warnings
4. **文档澄清**：正式 Studio 交付 = Scene `presentation.pptx`；LayoutPlan PPTX = critic / 布局轨

相关测试 12 通过。

### Backlog
- Workflow 仍双轨产出（layout_plan.pptx + 可选 from_scenes.pptx）
- Critic 截图仍绑 LayoutPlan PPTX，非 Studio Scene 预览
- `export_pptx_from_layout_plans` 命名误导（实际已是 Scene 导出）
- Marp / PresentationSpec `render.mjs` 遗留栈
- LayoutPlan 轨也应对齐 portable URI 解析

说「继续」进入 **Batch 12 QA / Delivery**。