# 发布等级与能力矩阵

> **目的：** 区分「有代码 / 有测试」与「真实用户可稳定使用」。  
> **更新：** 2026-07-23 · 与 [用户任务剧本](user-task-playbooks.md) 一起作为发版门槛。

## 发布等级

| 等级 | 含义 | 对外承诺 |
|------|------|----------|
| **Prototype** | 探索性实现，路径可能删除 | 不建议演示给客户 |
| **Experimental** | 主链可走通，边界与失败模式未验证 | 仅内部试用，需人工兜底 |
| **Preview** | 自动测试较全，真实项目验收未闭环 | 可演示；输出需人工校对 |
| **Beta** | 至少一个真实剧本验收通过，已知限制已文档化 | 可给友好用户试用 |
| **Stable** | 多项目验收 + 支持矩阵承诺 | 可作为交付默认路径 |
| **Deprecated** | 保留但不演进 | 迁移到正式路径 |

**读矩阵时：** 只有 **Beta / Stable** 才接近「可稳定使用」。`Experimental` / `Preview` 即使四列多为 ✅，也不等于产品完成。

## 列定义

| 列 | 含义 |
|----|------|
| **代码** | 仓库内有可用实现（非空 stub） |
| **自动测试** | unit / integration / golden / smoke 有覆盖 |
| **真实项目验收** | 完成 [用户任务剧本](user-task-playbooks.md) 中相关剧本，或等价脱敏项目验收记录 |
| **发布等级** | 上表之一；发版门槛以等级为准，不以「有测试」为准 |

图例：✅ 满足 · ⚠️ 部分 / 依赖外部工具或人工 · ❌ 未满足

## 能力矩阵（现行）

| 能力 | 代码 | 自动测试 | 真实项目验收 | 发布等级 |
|------|:----:|:--------:|:------------:|:--------:|
| 项目工作台（Streamlit） | ✅ | ✅ | ⚠️ | Preview |
| Mission / Workstream / DeliverablePlan | ✅ | ✅ | ⚠️ | Preview |
| 文档导入（PDF/DOCX/PPTX/XLSX/图片） | ✅ | ✅ | ⚠️ | Preview |
| 事实账本 / 素材看板 | ✅ | ✅ | ⚠️ | Experimental |
| LangGraph 汇报主链（Brief→Storyline→SlideSpec） | ✅ | ✅ | ⚠️ | Preview |
| JSON / Marp Markdown 导出 | ✅ | ✅ | ⚠️ | Preview |
| PPTX 导出（Marp CLI） | ✅ | ⚠️ | ❌ | Experimental |
| 原生元素 PPTX（PptxGen / LayoutPlan） | ✅ | ✅ | ⚠️ | Preview |
| PDF / 预览图（Marp） | ✅ | ⚠️ | ❌ | Experimental |
| 视觉编排（DesignSystem / LayoutPlan） | ✅ | ✅ | ⚠️ | Preview |
| Studio 画布（选中 / 多选 / 拖拽几何） | ✅ | ✅ | ⚠️ | Experimental |
| 评论 Inbox / 提案 / rebase | ✅ | ✅ | ❌ | Experimental |
| 容量预算与内容适配 | ✅ | ✅ | ❌ | Experimental |
| 图片衍生（原图保留 / 证据策略） | ✅ | ✅ | ❌ | Experimental |
| 叙事拆页 | ✅ | ✅ | ❌ | Experimental |
| Visual QA / Deck QA | ✅ | ✅ | ❌ | Experimental |
| 页面复活（slide recovery） | ✅ | ✅ | ❌ | Experimental |
| 模板归纳 / Template Studio | ✅ | ✅ | ❌ | Experimental |
| 质量审核与导出阻断 | ✅ | ✅ | ⚠️ | Preview |
| Legacy CLI / 文件整理 | ✅ | ⚠️ | ❌ | Deprecated |

## 发版规则（摘要）

1. **标签 `v0.2-beta` 之前：** 剧本 **A** 必须人工验收通过；其余剧本至少有自动化映射或明确 Waive。
2. **对外 Stable 声明之前：** 剧本 A–E 均需在脱敏真实项目上留下验收记录（见 `tests/e2e/real_projects/records/` 或 rehearsal session）。
3. 能力从 Experimental → Preview 至少要求：自动测试 ✅ 且主链可演示。
4. Preview → Beta 至少要求：对应剧本真实项目验收 ✅。

详见 [v0.2 Beta 发布决策](v0.2-beta-release-decision.md) 与 [用户任务剧本](user-task-playbooks.md)。
