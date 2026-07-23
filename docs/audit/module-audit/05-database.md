# 05 — Database

模块：ORM / Session / Alembic  
前缀：`DB-`  
更新：2026-07-23

| 编号 | 严重级别 | 状态 | 问题 | 文件 | 影响 | 修复方案 | 验收标准 | 提交 SHA |
|------|----------|------|------|------|------|----------|----------|----------|
| DB-001 | P0 | done | TransactionExecutor 会话中途 `commit` (DB1) | TransactionExecutor;（StudioSceneEdit 中途 commit 已去） | 部分提交、难回滚 | 成功路径末尾一次 commit；失败仅 rollback+flush 恢复，禁止随后 commit | 失败整单回滚；`test_failure_path_never_commits` | `-` |
| DB-002 | P0 | done | `create_all` + migration 001 no-op → 冷 Alembic 坏 (DB2) | alembic; bootstrap | 新库迁移链断裂 | 001 `create_all` 建基线；`init_database` 只走 Alembic | `test_cold_alembic_upgrade_creates_core_tables` | `-` |
| DB-003 | P0 | done | 失败路径 rollback 后再 commit (DB3) | TransactionExecutor | 脏数据落盘 | 失败只 rollback；禁止随后 commit | `test_failure_path_never_commits` | `-` |
| DB-004 | P1 | done | Application 直触 ORM (Batch 10) | repositories; layering 测试 | 分层破坏 | 经 Repository；守卫 | `test_application_does_not_import_orm_models` 绿 | `-` |
| DB-005 | P1 | done | 冗余 commit 散布 app/UI (~12+~40) (DB4) | ui; nested helpers; `test_commit_ownership` | 事务碎片 | UI 31 处 commit 移除；publisher / acceptance_metrics flush-only；边界 allowlist | `test_ui_does_not_call_session_commit` 等绿 | `-` |
| DB-006 | P1 | open | `CitationORM` 疑似死表 (DB5) | models | 迁移噪音 | 确认后删或接线 | 无引用或正式 API | `-` |
| DB-007 | P1 | done | llm/factory、pptxgen_renderer commit + 分层泄漏 (DB6) | pptxgen_renderer; session 策略 | infra 拥有事务 | pptxgen 改 flush；infra 守卫禁止 commit | `test_infrastructure_does_not_own_session_commit` 绿 | `-` |
| DB-008 | P2 | open | models 单体过大；UI→repo 捷径 (DB7/DB8) | `models.py`; ui | 难维护 | 拆分模型包；UI 只经 application | 分层测试扩展覆盖 | `-` |
