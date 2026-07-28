# 文档维护指南

## 事实源优先级

出现冲突时按以下顺序判断：运行中的代码与测试、自动生成文档、现行手写文档、带日期的发布/验收文档、历史分析与会话记录。历史总结不能证明当前功能仍存在，也不能定义当前 API。

## 版本语义（对外表述）

对外与对内沟通时，固定使用三条并行线，**不要混用**：

| 语义线 | 示例 | 说明 |
|--------|------|------|
| Software version | `v0.2.x-alpha` / `v0.2-beta` | 安装包与 git 标签；门禁见 [Beta 发布决策](v0.2-beta-release-decision.md) |
| Presentation Engine version | `v0.3` | 视觉引擎能力演进；计划见 [presentation-engine-v0.3.md](roadmap/presentation-engine-v0.3.md) |
| Product milestone | Showcase Candidate 1 | 对内展示与真实项目闭环目标 |

历史 **Stage / Round / Phase** 编号只写入 roadmap、review、session 文档，不得写入 README 顶部版本表或替代上述三条线。

修改版本表述时，至少同步：`README.md`、`docs/README.md`、`docs/architecture/current-system.md`，以及涉及发版或 Showcase 的决策文档。

## 代码变更对应文档

| 变更 | 至少检查 |
|---|---|
| CLI、安装依赖、启动方式 | `README.md`、`pyproject.toml`、部署文档 |
| 页面、按钮、用户流程 | `docs/studio-user-guide.md` 或对应 feature guide |
| 领域模型、主数据流、持久化边界 | `docs/architecture/current-system.md` 与专题架构文档；若改枚举/策略须同步文末 `arch-contract:*` 锚点，并跑 `tests/unit/test_architecture_contracts.py` |
| 视觉/画布/渲染 | `docs/visual/`、Studio 指南 |
| `Settings` 字段 | 运行 `python scripts/generate_config_docs.py`，不要手改生成文件 |
| 平台或外部工具支持 | 支持矩阵、跨平台验证、Quickstart |
| 发布门禁、版本表述 | 发布决策、rehearsal、README/`docs/README` 版本表、文档维护指南本节 |

## 写作约定

- 现行文档描述能力和边界，不使用模糊的“最新”“已全部完成”。
- 阶段号、日期和一次性验证结果放入 roadmap、review 或 session 文档。
- 功能状态至少区分“模型/服务存在”“已接 UI/主链”“有自动测试”“已人工验收”。
- 命令、类名、路径和默认值必须从仓库验证；配置默认值只引用自动生成参考。
- 删除或移动现行文档时同步更新 `README.md`、本目录索引和所有反向链接。

## 提交前检查

```bash
python scripts/generate_config_docs.py --check
python scripts/check_markdown_links.py
pytest tests/unit/test_config_reference_sync.py tests/unit/test_markdown_links.py -q
```

链接脚本检查仓库内相对目标是否存在；锚点语义、示例命令和用户界面名称仍需人工复核。历史会话中的 `computer://` URI 作为外部审计记录保留，不作为仓库文件目标。
