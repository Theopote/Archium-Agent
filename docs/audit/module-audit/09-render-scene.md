# 09 — Render scene

模块：RenderScene 编译、衍图、持久化  
前缀：`RS-`  
更新：2026-07-23

| 编号 | 严重级别 | 状态 | 问题 | 文件 | 影响 | 修复方案 | 验收标准 | 提交 SHA |
|------|----------|------|------|------|------|----------|----------|----------|
| RS-001 | P0 | done | 工作流与 Studio 编译链/衍图不一致 | SceneCompilerChain; ImageDerivativeService | 同页两套几何/图 | 共享链与服务 | 工作流与 Studio 同输入同 Scene 结构 | `-` |
| RS-002 | P0 | done | Scene id 不稳定；TEXT_OVERFLOW 策略不一 | compile / overflow_policy | 丢编辑；误报 | 按 layout_plan_id 复用；overflow 默认 warn | `arch-contract` overflow + id 复用测试 | `-` |
| RS-003 | P1 | open | LayoutPlan PPTX 仍为主轨，Scene 未成唯一 SSOT | compile + export | 双轨漂移 | Scene 正式交付；Plan 仅规划 | 正式 artifacts 以 Scene 为准 | `-` |
| RS-004 | P1 | open | 工作流持久化跳过 SceneRevision 历史 | scene persist | 无法回溯 | 写入 revision | 每次正式编译有 revision | `-` |
| RS-005 | P1 | open | Geometry QA 未进工作流 scene 环 | scene QA | 几何问题漏检 | 接入 compile 后环 | 失败可阻断或记 issue | `-` |
| RS-006 | P1 | done | template_studio 裸用 RenderSceneCompiler | `template_studio_service.py` | 缺链/衍图策略 | 走 SceneCompilerChain | 模板路径与主链一致 | `-` |
| RS-007 | P2 | accepted-debt | Chart 预览可能落主机路径；`storage_uri`≡`asset_path` | scene assets; QGS | 可移植性差 | URI 规范化；逐步拆字段 | 导出前均经 AssetPathResolver | `-` |
