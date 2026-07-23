**Batch 9（RenderScene）完成。**

### 已修
1. **统一编译路径**：workflow 改用 `SceneCompilerChain` + `ImageDerivativeService`（与 Studio 对齐）
2. **Scene ID 复用**：按 `layout_plan_id` 保留 id / 递增 version，避免孤儿行
3. **TEXT_OVERFLOW 复活**：`LayoutPlan.overflow_policy` WARN/SPLIT → TextNode `error`，语义 QA 可检出
4. **静默丢弃变警告**：缺 slide / 空编译 / 空文本 / `scene_repair_enabled=false` 均写入 warnings
5. **删除 Studio 死分支**（hash 相同却不可能再 save 的内层 if）
6. **QA 别名对齐**：`BEFORE_AFTER_UNPAIRED` / `PROJECT_PHOTO_WITHOUT_SOURCE` → slide 层已实现代码

相关测试通过；架构文档已更新。

### Backlog
- 主导出仍是 LayoutPlan PPTX，Scene PPTX 为第二轨（需收敛 SSOT）
- Workflow persist 仍不写 `SceneRevision` 历史
- Geometry QA 主要在 proposal，未进 workflow 场景环
- `template_studio_service` 仍用裸 `RenderSceneCompiler`
- Specialized compilers 多为 tag-only；`VisualCompositionService` 可删
- Chart `preview_storage_uri` 仍可能写主机路径

说「继续」进入 **Batch 10 Studio**。