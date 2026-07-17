# Archium Agent

Archium（阿基姆）是一款面向建筑师、规划师、设计院和建筑事务所的**智能汇报生产工具**。

它的目标不是简单地「让 AI 写一个 PPT」，而是：

> 读取建筑项目资料 → 理解项目事实和设计逻辑 → 根据汇报对象与目的组织叙事 → 生成可追溯、可编辑、可审核的汇报材料。

## 当前状态（v0.2 Stage 6）

| 能力 | 状态 |
|------|------|
| Streamlit 指令中心 UI | ✅ 可用 |
| 自然语言任务路由（CLI / Web） | ✅ 可用 |
| Pydantic 领域模型 | ✅ Stage 2 |
| SQLAlchemy + Repository 持久化 | ✅ Stage 3 |
| Marp PPT 快速生成 | ✅ 可用（需 API Key + Marp CLI） |
| AI 文件整理 | ✅ 可用（实验性） |
| Discord 消息守卫 | ✅ 可用（实验性） |
| LLM 抽象层 | ✅ Stage 4 |
| 文档导入（PDF/DOCX/PPTX/XLSX/图片） | ✅ Stage 5 |
| 汇报中间管线（Brief → Storyline → SlideSpec → JSON） | ✅ Stage 6 |
| LangGraph 多阶段工作流 | 🔜 Stage 7 |

## 核心架构（目标）

```
Project → SourceDocument → ProjectFact → PresentationBrief
       → Storyline → SlideSpec[] → Render (JSON / Marp / PPTX)
```

当前 v0.1 功能仍通过 `main.py` 路由到各模块；v0.2 正在逐步迁移到 `archium/` 包内的分层架构。

## 项目目录

```
Archium-Agent/
├── app.py                  # Streamlit 前端
├── main.py                 # CLI 入口 & 任务路由
├── config.py               # 向后兼容配置 shim
├── archium/                # v0.2 核心包
│   ├── config/settings.py  # pydantic-settings
│   ├── domain/             # Pydantic 领域模型
│   ├── application/        # ingestion_service、presentation_service 等
│   ├── agents/             # Brief / Storyline / Slide 生成 Agent
│   ├── infrastructure/
│   │   ├── database/       # SQLAlchemy ORM + Repository
│   │   ├── document_parsers/
│   │   ├── llm/
│   │   └── storage/
│   ├── exceptions.py       # 异常体系
│   └── logging.py          # 结构化日志
├── legacy/                 # 遗留/实验模块说明
├── data/                   # 运行时数据（项目、数据库、输出）
├── tests/                  # pytest 测试
└── pyproject.toml          # 依赖与工具配置
```

## 安装

### Windows

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev,legacy]"
copy .env.example .env
# 编辑 .env，填入 GEMINI_API_KEY（可选，无 Key 也可启动）
```

### macOS / Linux

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,legacy]"
cp .env.example .env
```

## 环境变量

| 变量 | 说明 | 必填 |
|------|------|------|
| `GEMINI_API_KEY` / `LLM_API_KEY` | OpenAI 兼容 API Key（如 Gemini） | 否（调用 LLM 时需要） |
| `LLM_BASE_URL` | API Base URL | 否 |
| `LLM_MODEL` | 模型名称，默认 `gemini-2.5-flash` | 否 |
| `MARP_COMMAND` | Marp CLI 命令，默认 `marp` | 否 |
| `DISCORD_BOT_TOKEN` | Discord Bot Token（遗留模块） | 否 |
| `DISCORD_USER_ID` | Discord 用户 ID（遗留模块） | 否 |

> **无 API Key 时应用可以正常启动**；只有执行 LLM 相关功能时才会提示未配置。

## 运行

```bash
# Streamlit Web UI
streamlit run app.py

# CLI 交互模式
python main.py
```

## 测试

```bash
pytest
ruff check archium
mypy archium

# 数据库迁移（可选，开发环境默认使用 init_database 自动建表）
alembic upgrade head
```

测试不依赖真实 API Key，使用临时目录，不会污染 `data/` 目录。

## Marp 安装

PPT 导出需要 [Marp CLI](https://github.com/marp-team/marp-cli)：

```bash
npm install -g @marp-team/marp-cli
marp --version
```

未安装 Marp 时，应用仍可启动；PPT 导出步骤会给出明确提示。

## 支持的文档格式（规划）

| 格式 | Stage 1 | 目标 Stage |
|------|---------|------------|
| PDF | — | Stage 5 |
| DOCX | — | Stage 5 |
| PPTX | — | Stage 5 |
| XLSX | — | Stage 5 |
| 图片 | — | Stage 5 |

## 数据保存位置

| 路径 | 用途 |
|------|------|
| `data/database/` | SQLite 数据库（Stage 3+） |
| `data/projects/` | 项目资料与资产 |
| `data/outputs/` | 生成的汇报文件 |
| `data/chroma/` | 向量索引（Stage 5+） |

## 隐私说明

- API Key 不会写入日志或代码
- 上传文件内容不会完整记录到日志
- 所有数据默认保存在本地

## 当前限制

- 尚无项目持久化；关闭应用后聊天记录不保留
- PPT 快速生成仍为「主题 → 一次 LLM → Marp」的单阶段模式（Stage 8 将接入新管线）
- Brief → Storyline → SlideSpec 管线已可用，但尚未接入 Streamlit UI 与 Marp 渲染
- Discord 与文件整理为实验性遗留功能

## 开发路线图

1. **Stage 1** — 工程基础（Settings、异常、日志、测试） ✅
2. **Stage 2** — Pydantic 领域模型 ✅
3. **Stage 3** — SQLAlchemy + Repository ✅
4. **Stage 4** — LLM 抽象层 ✅
5. **Stage 5** — 文档导入 ✅
6. **Stage 6** — 汇报中间管线 ✅
7. **Stage 7** — LangGraph 工作流
8. **Stage 8** — Marp 渲染迁移
9. **Stage 9** — Streamlit 项目工作台 UI

## 遗留模块

以下模块属于 v0.1 实验性功能，将在后续阶段移入 `legacy/` 并与主汇报流程解耦：

- `file_manager.py` — AI 辅助文件整理
- `discord_watcher.py` — Discord @ 消息优先级过滤

## License

Proprietary — internal use only.
