## Batch 16 — 文档与删除 ✅

### P0 已修
1. **README Marp 合并残留** — 去掉 `+` / 重复段落
2. **死入口 `archium-legacy`** — backlog 改为仓库内 `python -m legacy.main`（不进安装包）
3. **归档目标统一** — inventory / migration 清单对齐 `.dev-notes/docs-history/`（不再写 `docs/archive/`）
4. **危险清理计划** — `REPO_CLEANUP_PLAN.md` 标为 **superseded**，禁止执行其中的 `mv`/`rm`
5. **会话归档** — `docs/sessions/2026-07-*` → `.dev-notes/docs-history/sessions/`；`docs/sessions/README.md` 留指针
6. **根目录残留** — `CASCADE_DELETE_FIX.md` 迁入 `.dev-notes/docs-history/`

### 验证
`check_markdown_links.py` 通过；`test_markdown_links` + `test_legacy_isolation`：`4 passed`

### 文档
`current-system.md` 增加「文档分层」；`docs/README.md` 历史材料表已更新

### Backlog（未做，可后续）
| 项 | 说明 |
|---|---|
| `docs/delivery|implementation|analysis` 第二批 COMPLETE/FINAL | 仍在 `docs/`，可按 MIGRATION_CANDIDATES 再迁 |
| `RUFF_FIX_*` 指南 | 一次性策略笔记 |
| 未加 banner 的旧架构稿 | 如 `DECK_COMPOSITION_ARCHITECTURE.md` |

---

**模块体检 1–16 全部完成。** 未提交；需要的话可以说「提交」或指定要开的 PR。