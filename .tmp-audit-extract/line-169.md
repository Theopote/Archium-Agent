**Batch 10（Studio）完成。**

### 已修
1. **Accept 不再回滚 live**：提案 base/proposed 用独立快照行；状态更新只改 metadata，不再 `save` live scene
2. **`clear_proposal`**：只清 session 缓存，不再把已接受/拒绝提案标成 SUPERSEDED
3. **Accept 同步 LayoutPlan**：与 restore 相同，调用 `sync_layout_geometry_from_scene`
4. **去掉中途 commit**：`StudioSceneEditService` / 修订恢复依赖外层 session 提交

回归：`accept → live 文本 = proposed`；相关测试 79 通过。

### Backlog
- 双轨编辑仍在：proposal 环 vs `VisualEditService` / 版式直接编辑
- Studio 每次 load 仍可能 `ensure_scene_for_slide` 用 LayoutPlan 重编译覆盖已编辑 scene
- Proposal repo 未走 `save_render_scene` 护栏
- `apply_patch_actions` 缺节点时静默跳过
- 几何编辑双历史（VisualHistory + SceneHistory）
- 未挂载的 `ai_edit_panel` / 旧 `slide_canvas` 导出残留

说「继续」进入 **Batch 11 Rendering / PPTX**。