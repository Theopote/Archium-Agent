## 批次 5 Database：结论

Persistence 层整体可用（Repository 统一 flush、Domain 无 ORM 泄漏），主要风险在 **commit 归属混乱** 与 **迁移/bootstrap 双轨**。

### 结构速览

| 资产 | 规模 |
|------|------|
| ORM 表 | 42（`models.py` 单文件 ~1123 LOC） |
| Repository | 27 类 |
| Mapper | 3 模块，~82 对 |
| Alembic | 36 个 revision（head: `036_delivery_artifact_lineage`） |

Session：`get_session()` 在 Streamlit 用 scoped session，退出时 commit；Repository **只 flush**。

---

### 本轮已修（P1）

| 项 | 动作 |
|----|------|
| Application 直读 `ProjectORM` | 新增 `ProjectRepository.get_current_*()` 读取方法 |
| ORM 绕过 | `slide_semantic.py`、`template_studio_service.py` 改走 Repository |
| 守卫 | `test_application_does_not_import_orm_models` 锁住 application→models |

相关单测 9 passed。

---

### 剩余 backlog

| ID | 级 | 问题 |
|----|----|------|
| DB1 | P0 | `TransactionExecutor` / `StudioSceneEditService` 在 `get_session()` 内中途 `commit()` |
| DB2 | P0 | `create_all` + 001 no-op → 纯 Alembic 无法从零 bootstrap |
| DB3 | P0 | TransactionExecutor 失败路径 rollback 后再 commit |
| DB4 | P1 | Application/UI 多处冗余 `session.commit()`（~12 + ~40 处） |
| DB5 | P1 | `CitationORM` 疑似死表（无 repo / 无 migration create） |
| DB6 | P1 | `llm/factory.py`、`pptxgen_renderer.py` 依赖 application/UI 并 commit |
| DB7 | P2 | 单体 `models.py` / mega-repo；`scene_hash` 列与 payload 可能漂移 |
| DB8 | P2 | UI 大量直连 Repository（`studio_service`、`visual_service`） |

---

### 健康点

- Domain 完全无 SQLAlchemy
- Repository 内部模式一致（mapper + flush + `_handle_error`）
- Streamlit scoped session + WAL/busy_timeout 配置合理
- Alembic smoke 测试覆盖 ORM↔DB 表一致性
- `Project` 当前指针读写现已集中在 Repository

---

下一步按总表是 **批次 6 Parsing / Knowledge**（文档解析、事实账本、分块、引用与冲突）。需要的话直接继续。

[REDACTED]