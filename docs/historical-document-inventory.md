# 历史文档分类清单

本清单用于后续归档，不表示应立即删除文件。移动或删除前必须先通过 `python scripts/check_markdown_links.py`，并确认内容已被现行文档或版本历史覆盖。

## 默认保留但退出主导航

| 路径 | 类型 | 处理原则 |
|---|---|---|
| `docs/analysis/` | 专题分析 | 保留研究背景；文首补充日期和非现行提示 |
| `docs/delivery/` | 阶段交付 | 保留审计记录；不得作为当前能力依据 |
| `docs/implementation/` | 实现/修复总结 | 保留复盘；稳定知识应迁入架构或维护指南 |
| `docs/review/` | 审查快照 | 保留审查时点与结论，不持续维护 |
| `docs/sessions/` | 会话记录 | 按日期保存，不进入用户导航 |
| `docs/roadmap/` | 路线与验收草案 | 对照发布决策标明 active/superseded |

## 顶层历史文件

以下文件属于一次性总结，应从现行入口中移除，后续可统一迁入 `docs/archive/`：

- `docs/sessions/2026-07-20/README_UPDATE_SUMMARY.md`
- `docs/sessions/2026-07-20/SESSION_SUMMARY_2026-07-20.md`
- `docs/sessions/2026-07-20/COMPLETE_DELIVERY_SUMMARY.md`
- `docs/QUALITY_GATE_STATUS.md`（保留时必须标记生成/检查日期）

## 归档判定

满足以下条件才能移动：

1. 现行 README、用户指南、架构或发布决策不再引用该文件。
2. 文件没有唯一的运维步骤、数据迁移步骤或安全决策。
3. 有价值的长期知识已经合并到现行文档。
4. 移动后 Markdown 链接检查通过。

只有同时满足“内容已合并”和“版本历史可恢复”时才删除；否则使用归档而不是删除。
