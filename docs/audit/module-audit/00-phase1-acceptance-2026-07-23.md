# Archium-Agent 第一阶段验收报告（2026-07-23）

**验收结果：通过 — 进入下一阶段（Domain 逐文件深查）**  
**未达：** Beta 发布条件（仍为 Alpha / Preview）

## 总体结论

仓库已从「需要大规模整理」进入 **工程收敛**。第一轮工程治理完成，可正式进入逐模块增删改查。

路径：

```text
Alpha / Preview
    → 工程稳定化          ← 本阶段已通过
    → Domain 收敛         ← 下一阶段
    → 真实项目验收
    → Beta
```

## 验收重点与结果

| 重点 | 结果 |
|------|------|
| 工程骨架修复是否完成 | ✅ 通过（见 PF-*） |
| 模块审计体系是否建立 | ✅ 通过（`docs/audit/module-audit/`） |
| 第一阶段遗留问题是否关闭 | ✅ 通过（骨架类）；业务 P0 仍开放但不挡深查 |
| 是否具备 Domain → Application → Workflow 深查条件 | ✅ 具备 |

## 已完成的重要修复

| 项 | 台账 | 判断 |
|----|------|------|
| Legacy 隔离（不进安装包，仅仓库内） | PF-001 done；PF-010 accepted-debt | 正确；不建议现在删除；v0.3 再议迁仓 |
| 依赖锁定（uv lock + CI） | PF-004 done | 通过 |
| 静态检查范围对齐 | PF-006 done | 通过 |
| CI 分层 | PF-007 done | 通过 |
| 发布能力矩阵 / 勿把「有代码+测试」当可生产 | PF-008 done | 通过 |
| 双入口 bootstrap / 架构合同 / 剧本门禁等 | PF-002…PF-009 | 通过 |

## 模块审计体系

`docs/audit/module-audit/` 已建立（`00` 判断与本验收、`01`–`14` 模块台账）。Issue 用稳定前缀（`PF-`/`DOM-`/…），不用 Stage/Round/Phase 批次名。

## 开放 P0（不挡深查，挡 Beta）

| 编号 | 模块 | 状态 |
|------|------|------|
| WF-002 | Workflow checkpoint 竞态 | open |
| DB-001 | TransactionExecutor 中途 commit | open |
| DB-002 | create_all + Alembic 冷启动 | open |
| DB-003 | rollback 后再 commit | open |
| KN-001 | 事实主键冲突丢 alternate | open |
| APP-002 | Spec / Scene 双导出路径 | open |
| QD-010 | 人工视觉门禁 | open |
| TS-010 | 真实用户剧本 A（B10） | open |

**补充（相对验收初稿）：**

- **DOM-011**（LayoutPlan / RenderScene 几何 SSOT）已在 Domain 开查首轮 **关闭**，不再列入开放 P0。
- **TS-008** chromadb CVE 为 **mitigated**（allowlist → 2026-10-01），不挡深查。

## 最重要判断

最大风险已从「功能不足」转为 **复杂度管理**：重复、断链、状态不一致、维护成本。见 [00-round1-judgment.md](00-round1-judgment.md)。

## 评分（验收时点）

| 领域 | 评分 |
|------|------|
| 产品定位 | 9/10 |
| 架构设计 | 8.5/10 |
| 工程治理 | 9/10 |
| 测试体系 | 8/10 |
| 真实用户闭环 | 6.5/10 |
| Domain 稳定性 | 深查中（见 [02-domain-file-audit.md](02-domain-file-audit.md)） |
| Beta 准备度 | 7/10 |

## 下一阶段

**Archium Domain 模块逐文件审查** — 输出格式：文件 → 问题 → 严重级别 → 是否删除/合并/重构 → 修改方案 → 验收条件。

入口：[02-domain-file-audit.md](02-domain-file-audit.md) · 台账汇总：[02-domain.md](02-domain.md)
