# Migration Candidates

以下文档更适合作为开发过程记录保存在 `.dev-notes/docs-history/`，而不是继续占据正式 `docs/` 文档面。

## 已完成（Batch 16）

`docs/sessions/` 整体迁至 `.dev-notes/docs-history/sessions/`；`docs/sessions/README.md` 保留为指针页。

## 第一批：高优先级（会话 — 已迁移）

- `.dev-notes/docs-history/sessions/2026-07-20/SESSION_SUMMARY_2026-07-20.md`
- `.dev-notes/docs-history/sessions/2026-07-20/README_UPDATE_SUMMARY.md`
- `.dev-notes/docs-history/sessions/2026-07-20/COMPLETE_DELIVERY_SUMMARY.md`
- `.dev-notes/docs-history/sessions/2026-07-19/2026-07-19-work-summary.md`
- `.dev-notes/docs-history/sessions/2026-07-19/COMPLETE_SESSION_SUMMARY.md`
- `.dev-notes/docs-history/sessions/2026-07-19/SESSION_INTEGRATION_FIXES_COMPLETE.md`
- `.dev-notes/docs-history/sessions/2026-07-19/SESSION_SUMMARY_E2E_FIX_COMPLETE.md`
- `.dev-notes/docs-history/sessions/2026-07-19/WORK_SUMMARY_2026-07-19_SESSION_RESUMED.md`

## 第二批：建议归档（仍在 `docs/`）

- `docs/delivery/DELIVERY_CHECKLIST.md`
- `docs/delivery/FINAL_PROJECT_SUMMARY.md`
- `docs/delivery/IMPLEMENTATION_SUMMARY.md`
- `docs/analysis/Archium项目审查报告.md`
- `docs/implementation/DOCS_ORGANIZATION_COMPLETE.md`
- `docs/guides/RUFF_FIX_STRATEGY.md`
- `docs/guides/RUFF_FIX_FINAL_RECOMMENDATION.md`

## 保留在 `docs/` 的正式文档示例

- `docs/README.md`
- `docs/configuration-reference.md`
- `docs/studio-user-guide.md`
- `docs/architecture/current-system.md`
- `docs/visual/**`
- `docs/deployment/**`（部署工作按 hygiene 延期，文档仅参考）
- `docs/branch-protection.md`
- `docs/*validation*`
- `docs/*release*`

## 迁移原则

1. 面向用户、协作者、部署、运行、架构理解的稳定文档保留在 `docs/`。
2. 面向一次性实施、交付回执、工作日志、会话总结的文档迁入 `.dev-notes/docs-history/`。
3. 迁移前优先加上历史说明；迁移后原路径用短指针页或更新索引。
4. **禁止**执行已 superseded 的 `docs/guides/REPO_CLEANUP_PLAN.md` 中的批量 `rm`。
