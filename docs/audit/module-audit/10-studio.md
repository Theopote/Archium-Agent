# 10 — Studio

模块：Studio 编辑、提案、选区  
前缀：`ST-`  
更新：2026-07-23

| 编号 | 严重级别 | 状态 | 问题 | 文件 | 影响 | 修复方案 | 验收标准 | 提交 SHA |
|------|----------|------|------|------|------|----------|----------|----------|
| ST-001 | P0 | done | 接受提案会回滚 live scene | `scene_proposal_service.py` | 接受即丢编辑 | 快照行；接受不 rollback live | 接受后画布保留接受结果 | `-` |
| ST-002 | P0 | done | clear_proposal 误提交；accept 不同步 LayoutPlan；中途 commit | StudioSceneEdit | 脏事务 / Plan 脱节 | session-only clear；同步 Plan；去中途 commit | 单测覆盖 accept/clear | `-` |
| ST-003 | P1 | open | 提案环 vs VisualEdit 双编辑环 | studio services | 状态分叉 | 统一命令模型 | 一种写路径进 Scene | `-` |
| ST-004 | P1 | mitigated | load 可能对已编辑页重编译覆盖 | `ensure_scene_for_slide` | 丢用户改动 | DOM-011：`geometry_authority=render_scene` 时非 force 复用 Scene | `test_ensure_scene_preserves_render_scene_geometry_authority` | `-` |
| ST-005 | P1 | open | Proposal repo 绕过 `save_render_scene` 守卫 | proposal persistence | 坏 Scene 入库 | 统一保存入口 | 守卫测试覆盖提案路径 | `-` |
| ST-006 | P2 | done | 双历史；死 `ai_edit_panel` / `slide_canvas` | ui/studio | 维护噪音 | 删死代码；历史单一 | 无未引用模块 | `-` |
| ST-007 | P1 | open | Studio 真人验收不足（矩阵 Experimental） | release matrix; playbook E | 不能宣称可用 | 剧本 E 记录 | 矩阵升 Preview/Beta 有证据 | `-` |
