# 11 — Rendering / PPTX

模块：PptxGen / 导出适配 / 多渲染栈  
前缀：`RP-`  
更新：2026-07-23

| 编号 | 严重级别 | 状态 | 问题 | 文件 | 影响 | 修复方案 | 验收标准 | 提交 SHA |
|------|----------|------|------|------|------|----------|----------|----------|
| RP-001 | P0 | done | 进 Node 前未解析可移植 URI | `AssetPathResolver`; `scene_pptx_adapter` | 跨机丢图 | 导出前 resolve | smoke/golden 图资源可打开 | `-` |
| RP-002 | P1 | open | 工作流双输出 layout_plan.pptx + from_scenes | workflow export | 用户不知信哪个 | 单一正式 artifact 名 | 交付清单只有一个主 PPTX | `-` |
| RP-003 | P1 | open | Critic 截图绑 LayoutPlan PPTX | critic / screenshots | 评的不是 Scene 稿 | 绑正式 Scene 导出 | 截图源 = 交付文件 | `-` |
| RP-004 | P2 | open | `export_pptx_from_layout_plans` 名实不符；Marp/Spec 栈并存 | exporters | 误导 | 改名/弃用；矩阵标 Experimental | 文档与符号一致 | `-` |
| RP-005 | P0 | open | FILL 路由非真正原地 OOXML（QGS partial） | fill native template | 模板结构被冲 | 原地填充或降级声明 | QGS FILL 项 Done 或矩阵诚实降级 | `-` |
