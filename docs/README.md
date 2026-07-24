# Archium 文档中心

本目录同时保存**现行文档**与**历史工程记录**。使用、部署或开发 Archium 时，应优先阅读本页列出的现行文档；`analysis/`、`delivery/`、`implementation/`、`review/`、`sessions/` 中的材料只描述某次检查或交付时点，不能替代当前代码与现行文档。

## 从这里开始

| 读者 | 首选文档 |
|---|---|
| 首次使用 | [项目 README](../README.md) · [Docker 快速启动](deployment/docker-quickstart.md) |
| 汇报制作人员 | [汇报工作室用户指南](studio-user-guide.md) |
| 视觉与模板人员 | [视觉编排文档](visual/README.md) |
| 部署维护人员 | [配置参考](configuration-reference.md) · [跨平台支持](beta-platform-support-matrix.md) |
| 开发者 | [当前系统架构](architecture/current-system.md) · [管线角色](architecture/pipeline-roles.md) · [贡献指南](../CONTRIBUTING.md) |
| Beta 验收 | [发布决策](v0.2-beta-release-decision.md) · [演练流程](v0.2-beta-rehearsal.md) · [用户任务剧本](user-task-playbooks.md) |

## 现行文档

### 产品与操作

- [汇报工作室用户指南](studio-user-guide.md)：浏览、画布编辑、内容适配、评论提案、检查与导出。
- [项目任务与自适应规划](project-mission-adaptive-planning.md)：Mission、Workstream、DeliverablePlan。
- [项目管理页](features/PROJECT_MANAGEMENT_PAGE.md)：项目列表与生命周期操作。

### 架构与视觉

- [当前系统架构](architecture/current-system.md)：代码目录、主数据流、界面与主要边界的当前快照。
- [管线角色](architecture/pipeline-roles.md)：逻辑角色与应用服务的映射（六席硬上限）。
- [Vision Intelligence Layer](architecture/vision-intelligence-layer.md)：建筑语义驱动的概念/图示/氛围生成（Visual 席位；非 Midjourney 套壳）。
- [视觉编排](visual/README.md)：VisualIntent、LayoutPlan、RenderScene、Studio 编辑与 QA。
- [配置参考](configuration-reference.md)：由 `Settings` 自动生成，禁止手工修改。

### 部署、测试与发布

- [Docker 快速启动](deployment/docker-quickstart.md)与[测试清单](deployment/docker-test-checklist.md)。
- [跨平台验证](cross-platform-validation.md)与[Beta 平台支持矩阵](beta-platform-support-matrix.md)。
- [真实项目验证准备](real-project-validation-preparation.md)。
- [发布等级与能力矩阵](release-capability-matrix.md)。
- [关键用户任务剧本 A–E](user-task-playbooks.md)。
- [v0.2 Beta 发布决策](v0.2-beta-release-decision.md)。
- [模块检查台账](audit/module-audit/README.md)：按模块与 Issue ID 跟踪架构/质量问题（不用 Stage/Round/Phase）。
- [第一阶段验收（2026-07-23）](audit/module-audit/00-phase1-acceptance-2026-07-23.md) · [Domain 逐文件审计](audit/module-audit/02-domain-file-audit.md)。

## 历史材料

以下目录保留决策背景和审计轨迹，但其中的“已完成”“当前状态”“下一步”均以文档日期为准：

| 目录 | 性质 |
|---|---|
| `analysis/` | 专题分析与差距检查 |
| `delivery/` | 阶段性交付总结 |
| `implementation/` | 实现记录和修复复盘 |
| `review/` | 代码/测试审查快照 |
| `roadmap/` | 规划与验收草案；是否仍有效需对照发布决策 |
| `.dev-notes/docs-history/sessions/` | 工作会话记录（已从 `docs/sessions/` 迁出） |

`docs/sessions/README.md` 仅为指针页。带日期的 session summary 与一次性交付总结统一归入 `.dev-notes/docs-history/`。

## 维护规则

修改用户可见行为、CLI、配置、数据流或支持矩阵时，代码变更应同步修改相应现行文档。详细规则和检查清单见 [文档维护指南](documentation-maintenance.md)；归档候选与删除条件见[历史文档分类清单](historical-document-inventory.md)。
