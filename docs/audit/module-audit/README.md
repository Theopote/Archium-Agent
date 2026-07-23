# 模块检查台账

**用途：** 按稳定模块记录架构 / 质量问题，跟踪修复与验收。  
**更新：** 2026-07-23  
**原则：** 不再用 Stage / Round / Phase 命名修复批次；统一用 **模块文件 + Issue ID**。

## 目录

| 文件 | 模块 | 前缀 |
|------|------|------|
| [00-round1-judgment.md](00-round1-judgment.md) | 第一轮最终判断（工程收敛） | — |
| [00-phase1-acceptance-2026-07-23.md](00-phase1-acceptance-2026-07-23.md) | 第一阶段验收通过报告 | — |
| [01-project-foundation.md](01-project-foundation.md) | 工程骨架 / 打包 / CI / 文档契约 | `PF-` |
| [02-domain.md](02-domain.md) | Domain 模型与分层（Issue 台账） | `DOM-` |
| [02-domain-file-audit.md](02-domain-file-audit.md) | Domain 逐文件深查（删/并/重构） | — |
| [03-application.md](03-application.md) | Application 服务 | `APP-` |
| [04-workflow.md](04-workflow.md) | LangGraph 工作流 | `WF-` |
| [05-database.md](05-database.md) | ORM / 会话 / 迁移 | `DB-` |
| [06-parsing-knowledge.md](06-parsing-knowledge.md) | 解析与事实/知识 | `KN-` |
| [07-mission-storyline.md](07-mission-storyline.md) | Mission / Storyline / Plan | `MS-` |
| [08-visual-planning.md](08-visual-planning.md) | VisualIntent / LayoutPlan / 容量 | `VP-` |
| [09-render-scene.md](09-render-scene.md) | RenderScene 编译与持久化 | `RS-` |
| [10-studio.md](10-studio.md) | Studio 编辑与提案 | `ST-` |
| [11-rendering-pptx.md](11-rendering-pptx.md) | PPTX / 渲染出口 | `RP-` |
| [12-qa-delivery.md](12-qa-delivery.md) | QA / 导出门禁 / 交付 | `QD-` |
| [13-ui.md](13-ui.md) | Streamlit / Canvas UI | `UI-` |
| [14-tests-security.md](14-tests-security.md) | 测试分层 / 配置 / 依赖安全 | `TS-` |

## Issue 字段（强制）

每条问题必须包含：

| 字段 | 说明 |
|------|------|
| **编号** | `{前缀}-{三位序号}`，模块内唯一且永不复用（关闭后也不改号） |
| **模块** | 上表模块名 |
| **文件** | 主要路径（可多个，用 `;` 分隔） |
| **严重级别** | `P0` 阻断正确性/数据/安全 · `P1` 明显债务/双轨 · `P2` 卫生/清理 |
| **问题** | 一句话现象（可括号注明旧 ID，如 `W2`） |
| **影响** | 用户或系统后果 |
| **修复方案** | 拟定做法（未修也可写） |
| **验收标准** | 可执行的通过条件（测试命令 / 行为断言） |
| **状态** | 见下表 |
| **提交 SHA** | 合入修复的 commit；未合入写 `-`；多 commit 写主 SHA |

### 状态枚举

| 状态 | 含义 |
|------|------|
| `open` | 未修 |
| `in_progress` | 正在改 |
| `done` | 已合入并通过验收 |
| `mitigated` | 风险降低但根因未消（须写到期或复查条件） |
| `accepted-debt` | 明确接受，附 Owner / 复查日 |
| `blocked-external` | 卡在上游或真人验收 |

### 不要做的事

- 不要新建 `COMPLETE_*` / `SESSION_SUMMARY_*` 代替本台账更新。
- 不要用 Stage / Round / Phase / Batch 作为 Issue 编号（历史 Batch 结论已映射进本台账）。
- Beta 产品项继续用 `docs/v0.2-beta-backlog.md` 的 `B*`；台账中可交叉引用，不另造发布批次名。

## 相关现行文档

- [当前系统架构](../../architecture/current-system.md)
- [发布等级矩阵](../../release-capability-matrix.md)
- [用户任务剧本](../../user-task-playbooks.md)
- [依赖安全 triage](../../security/AUDIT_TRIAGE_2026-07.md)
- [质量门禁状态](../../QUALITY_GATE_STATUS.md)
- [v0.2 Beta backlog](../../v0.2-beta-backlog.md)

## 如何新增一条

1. 选对模块文件，取该文件下一个空序号。
2. 填满十个字段；`open` 时 SHA 为 `-`。
3. 合入后把状态改为 `done` 并填 SHA；同步更新本 README「开放 P0 一览」若涉及 P0。

## 开放 P0 一览（2026-07-24）

| 编号 | 模块 | 一句话 |
|------|------|--------|
| [DB-001](05-database.md) | database | TransactionExecutor 会话中途 `commit` |
| [DB-002](05-database.md) | database | `create_all` + Alembic 001 no-op 冷启动 |
| [DB-003](05-database.md) | database | 失败路径 rollback 后再 commit |
| [KN-001](06-parsing-knowledge.md) | knowledge | 事实主键冲突丢弃 alternate 值 |
| [APP-003](03-application.md) | application | `session.commit` 所有权不一致 |
| [QD-010](12-qa-delivery.md) | qa-delivery | 正式人工视觉门禁未过 |
| [TS-010](14-tests-security.md) | tests-security | 非开发者剧本 A + 修改成本（Beta B10） |

P0 已关闭：`WF-002`（checkpoint 串行化）；`TS-008` chromadb CVE **mitigated**（allowlist → 2026-10-01）。

Domain 台账主线已收敛；余项见 [02-domain.md](02-domain.md)（如 DOM-008/013…）。已关闭：`DOM-003`/`DOM-004`/`DOM-005`/`DOM-006`/`DOM-007`/`DOM-009`/`DOM-011`/`DOM-012`/`DOM-014`/`DOM-015`/`DOM-016`/`DOM-017`/`DOM-018`/`DOM-020`。逐文件审计见 [02-domain-file-audit.md](02-domain-file-audit.md)。
