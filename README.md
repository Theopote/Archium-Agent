# Archium Agent

Archium（阿基姆）是一款面向建筑师、规划师、设计院和建筑事务所的**智能汇报生产工具**。

它的目标不是简单地「让 AI 写一个 PPT」，而是：

> 读取建筑项目资料 → 理解项目事实和设计逻辑 → 根据汇报对象与目的组织叙事 → 生成可追溯、可编辑、可审核的汇报材料。

## 版本与成熟度

| 项 | 值 |
|----|-----|
| **Current version** | v0.2-alpha.3 |
| **Architecture stage** | Stage 15 implemented |
| **Stability status** | Alpha |
| **Production readiness** | Not ready |

> Alpha 阶段功能可以演示和内部试用，但不保证 API、数据模型或输出格式的长期稳定；请勿直接用于生产交付。

## 能力矩阵

| 功能 | 已实现 | 有测试 | 已接主流程 | 可稳定使用 |
|------|:------:|:------:|:----------:|:----------:|
| 项目工作台（Streamlit UI） | ✅ | ✅ | ✅ | ⚠️ |
| 文档导入（PDF/DOCX/PPTX/XLSX/图片） | ✅ | ✅ | ✅ | ⚠️ |
| 语义分块与资料片段编辑 | ✅ | ✅ | ✅ | ⚠️ |
| 向量检索（Chroma + Embedding） | ✅ | ⚠️ | ✅ | ⚠️ |
| LangGraph 多阶段工作流 | ✅ | ✅ | ✅ | ⚠️ |
| Brief / Storyline / SlideSpec 审核 | ✅ | ✅ | ✅ | ⚠️ |
| 统一修订历史（Brief / Storyline / SlideSpec lineage） | ✅ | ✅ | ✅ | ⚠️ |
| SlideSpec 字段 diff | ✅ | ✅ | ✅ | ⚠️ |
| JSON 导出 | ✅ | ✅ | ✅ | ⚠️ |
| Marp Markdown 导出 | ✅ | ✅ | ✅ | ⚠️ |
| PPTX 导出（Marp CLI） | ✅ | ⚠️ | ✅ | ❌ |
| PDF 导出（Marp CLI） | ✅ | ⚠️ | ✅ | ❌ |
| 幻灯片预览图（Marp `--images` PNG） | ✅ | ✅ | ✅ | ⚠️ |
| 项目事实账本（Fact Ledger） | ✅ | ✅ | ✅ | ⚠️ |
| 素材看板（Asset Board） | ✅ | ✅ | ✅ | ⚠️ |
| 四层质量审核（内容/证据/建筑/版面） | ✅ | ✅ | ✅ | ⚠️ |
| 质量审核与导出阻断 | ✅ | ✅ | ✅ | ⚠️ |
| CLI 指令中心（`main.py`） | ✅ | ⚠️ | — | ❌ |
| 遗留实验模块（文件整理 / Discord） | ✅ | ⚠️ | — | ❌ |

图例：✅ 已满足 · ⚠️ 部分满足或依赖外部工具 · ❌ 未满足或不稳定

## 应用入口

| 入口 | 命令 | 地位 | 说明 |
|------|------|------|------|
| **主入口** | `streamlit run app.py` | v0.2 正式路径 | 项目工作台、结构化汇报管线、Brief/Storyline/SlideSpec 审核 |
| **CLI 辅助** | `python main.py` | 遗留/实验 | 自然语言路由到 v0.1 工具（文件整理、快速 PPT、Discord 守卫） |
| **库 API** | `archium/` 包内服务 | v0.2 核心 | `PresentationWorkflowService`、`IngestionService` 等 |

`main.py` 与 `ppt_generator.py` 属于快速原型路径，**不等同**于项目工作台内的 Brief → Storyline → SlideSpec 主流程。

## 导出格式

主流程通过 `RenderResult` 统一返回导出路径：

```python
@dataclass
class RenderResult:
    json_path: Path | None
    markdown_path: Path | None
    pptx_path: Path | None
    pdf_path: Path | None
    preview_images: list[Path]
    warnings: list[str]
```

| 格式 | 主流程 | 实现 | 依赖 |
|------|:------:|------|------|
| **JSON** | ✅ | `JsonPresentationRenderer` | 无 |
| **Marp Markdown** | ✅ | `MarpPresentationRenderer.render()` | 无 |
| **PPTX** | ✅（可选） | `MarpPresentationRenderer.export_pptx()` | Marp CLI |
| **PDF** | ✅（可选） | `MarpPresentationRenderer.export_pdf()` | Marp CLI |
| **预览图 PNG** | ✅（可选） | `MarpPresentationRenderer.export_preview_images()` | Marp CLI（`--images`） |

PPTX / PDF / 预览图转换失败不会阻断 Markdown 导出，错误写入 `RenderResult.warnings`。预览图默认写入 `data/outputs/presentations/{id}/v{n}/previews/presentation.001.png` 等文件，并在工作台结果区展示缩略图。

## 核心架构

```
Project → SourceDocument → ProjectFact → PresentationBrief
       → Storyline → SlideSpec[] → Render (JSON / Markdown / PPTX / PDF)
```

## 项目目录

```
Archium-Agent/
├── app.py                  # Streamlit 前端
├── main.py                 # CLI 入口 & 任务路由
├── config.py               # 向后兼容配置 shim
├── archium/                # v0.2 核心包
│   ├── config/settings.py  # pydantic-settings
│   ├── domain/             # Pydantic 领域模型
│   ├── application/        # ingestion_service、presentation_service、workflow 等
│   ├── agents/             # Brief / Storyline / Slide 生成 Agent
│   ├── workflow/           # LangGraph 工作流编排
│   ├── ui/                 # Streamlit 页面与服务
│   ├── infrastructure/
│   │   ├── database/       # SQLAlchemy ORM + Repository
│   │   ├── document_parsers/
│   │   ├── llm/
│   │   ├── renderers/      # JSON / Marp 导出
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
pip install -e ".[full,dev,legacy]"
copy .env.example .env
# 编辑 .env，填入 GEMINI_API_KEY（可选，无 Key 也可启动）
```

### macOS / Linux

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[full,dev,legacy]"
cp .env.example .env
```

## 环境变量

| 变量 | 说明 | 必填 |
|------|------|------|
| `DATABASE_PATH` | SQLite 数据库文件路径（相对项目根目录），默认 `data/database/archium.db` | 否 |
| `DATABASE_URL` | SQLAlchemy 连接 URL 覆盖项（未设置时使用 `DATABASE_PATH`） | 否 |
| `GEMINI_API_KEY` / `LLM_API_KEY` | OpenAI 兼容 API Key（如 Gemini） | 否（调用 LLM 时需要） |
| `LLM_BASE_URL` | API Base URL | 否 |
| `LLM_MODEL` | 模型名称，默认 `gemini-2.5-flash` | 否 |
| `EMBEDDING_API_KEY` | Embedding 专用 API Key（未设置时回退到 LLM Key） | 否 |
| `EMBEDDING_BASE_URL` | Embedding API Base URL（未设置时回退到 LLM Base URL） | 否 |
| `EMBEDDING_MODEL` | Embedding 模型名称 | 否（启用向量检索时需要） |
| `RETRIEVAL_ENABLED` | 是否启用向量检索，默认 `false` | 否 |
| `WORKFLOW_CHECKPOINT_PATH` | LangGraph SqliteSaver checkpoint 路径 | 否 |
| `BLOCK_EXPORT_ON_CRITICAL_REVIEW` | 为 `true` 时，未处理的严重审核问题将阻断 JSON/Marp 导出 | 否 |
| `LLM_PROFESSIONAL_REVIEW_ENABLED` | 为 `true` 且已配置 LLM 时，额外运行 LLM 专业审核 | 否 |
| `FACT_EXTRACTION_ENABLED` | 为 `true` 且 LLM 可用时，在检索上下文后提取 ProjectFact | 否 |
| `SLIDE_REPAIR_ENABLED` | 为 `true` 且 LLM 可用时，自动修复页面级严重/高优先级审核问题 | 否 |
| `MARP_COMMAND` | Marp CLI 命令，默认 `marp` | 否 |
| `MARP_PREVIEW_IMAGES_ENABLED` | 导出 Marp Markdown 时是否生成 PNG 预览图，默认 `true` | 否 |
| `MARP_PREVIEW_IMAGE_FORMAT` | 预览图格式（`png` 或 `jpeg`），默认 `png` | 否 |
| `DISCORD_BOT_TOKEN` | Discord Bot Token（遗留模块） | 否 |
| `DISCORD_USER_ID` | Discord 用户 ID（遗留模块） | 否 |

> **无 API Key 时应用可以正常启动**；只有执行 LLM 相关功能时才会提示未配置。

## 运行

```bash
# 主入口：Streamlit 项目工作台 + 结构化汇报管线
streamlit run app.py

# 辅助入口：CLI 自然语言路由（遗留 v0.1 工具）
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

PPTX / PDF 导出需要 [Marp CLI](https://github.com/marp-team/marp-cli)：

```bash
npm install -g @marp-team/marp-cli
marp --version
```

未安装 Marp 时，应用仍可启动；PPT 导出步骤会给出明确提示。

未安装 Marp 时，应用仍可启动并完成 JSON / Marp Markdown 导出；勾选 PPTX 或 PDF 时会在 `RenderResult.warnings` 中提示。

## 支持的文档格式

| 格式 | 导入 | 解析 | 分块 | 向量索引 |
|------|:----:|:----:|:----:|:--------:|
| PDF | ✅ | ✅ | ✅ | ⚠️（需启用检索） |
| DOCX | ✅ | ✅ | ✅ | ⚠️ |
| PPTX | ✅ | ✅ | ✅ | ⚠️ |
| XLSX | ✅ | ✅ | ✅ | ⚠️ |
| 图片 | ✅ | ✅ | — | — |

导入能力在 Stage 5 完成；语义分块与片段编辑在 Stage 10–11 增强。

## 数据保存位置

| 路径 | 用途 |
|------|------|
| `data/database/` | SQLite 数据库（Stage 3+） |
| `data/projects/` | 项目资料与资产 |
| `data/outputs/` | 生成的汇报文件 |
| `data/chroma/` | Chroma 向量索引（Stage 10） |

## 隐私说明

- API Key 不会写入日志或代码
- 上传文件内容不会完整记录到日志
- 所有数据默认保存在本地

## 当前限制

- 指令中心聊天记录仍保存在浏览器 Session 中，关闭页面后会丢失
- 项目工作台已支持项目持久化、资料导入、汇报生成与 Brief / Storyline / SlideSpec 审核编辑
- 文档导入后按语义边界切分（段落合并、递归切分、重叠窗口），超长段落可选 Embedding 断点检测
- 工作台支持预览/编辑资料片段，保存后同步更新向量索引
- Brief、Storyline、SlideSpec 均支持基于 `lineage_id` 的统一修订历史；SlideSpec 另支持字段 diff 与 unified diff 对比
- 项目事实账本（Fact Ledger）支持标准键提取、冲突检测与人工确认；已确认事实优先注入生成上下文
- 素材看板（Asset Board）支持视觉需求扁平化视图、素材匹配、人工指定与确认
- 四层质量审核：内容层、证据层、建筑专业层、版面层；严重问题可阻断导出
- 驳回后可一键重新生成 Brief、Storyline 或 Slide 计划
- PPTX / PDF 导出依赖 Marp CLI；未安装时仍可导出 JSON 与 Marp Markdown，警告写入 `RenderResult.warnings`
- Discord 与文件整理为实验性遗留功能

## 开发路线图

1. **Stage 1** — 工程基础（Settings、异常、日志、测试） ✅
2. **Stage 2** — Pydantic 领域模型 ✅
3. **Stage 3** — SQLAlchemy + Repository ✅
4. **Stage 4** — LLM 抽象层 ✅
5. **Stage 5** — 文档导入 ✅
6. **Stage 6** — 汇报中间管线 ✅
7. **Stage 7** — LangGraph 工作流 ✅
8. **Stage 8** — Marp 渲染迁移 ✅
9. **Stage 9** — Streamlit 项目工作台 UI ✅
10. **Stage 10** — 向量检索增强（Chroma + Embedding） ✅
11. **Stage 11** — 资料片段管理 + 引用溯源 ✅
12. **Stage 12** — 统一修订历史（Brief / Storyline / SlideSpec lineage + SlideSpec diff） ✅
13. **Stage 13** — 项目事实账本（Fact Ledger · 提取 / 冲突检测 / 人工确认） ✅
14. **Stage 14** — 素材看板（Asset Board · 匹配 / 指定 / 确认 / 裁剪标记） ✅
15. **Stage 15** — 四层质量审核（Content / Evidence / Architectural / Layout Reviewer） ✅
16. **Stage 16** — PresentationSpec → PptxGenJS 可编辑 PPTX（规划中）

## 遗留模块

以下模块属于 v0.1 实验性功能，将在后续阶段移入 `legacy/` 并与主汇报流程解耦：

- `file_manager.py` — AI 辅助文件整理
- `discord_watcher.py` — Discord @ 消息优先级过滤

## License

Proprietary — internal use only.
