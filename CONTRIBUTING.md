# Contributing to Archium

感谢关注阿基姆（Archium）。本项目以 **MIT** 许可开源，欢迎 Issue、讨论与 Pull Request。

## 行为准则

参与前请阅读 [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)。

## 开发环境

要求：**Python 3.11+**。可选：Node.js（PptxGenJS）、Marp CLI（预览导出）。

```bash
git clone https://github.com/Theopote/Archium-Agent.git
cd Archium-Agent
python -m venv .venv
# Windows PowerShell:
#   .venv\Scripts\Activate.ps1
# macOS / Linux:
#   source .venv/bin/activate
pip install -e ".[full,dev]"
copy .env.example .env   # Linux/macOS: cp .env.example .env
```

在 `.env` 中配置 LLM（例如 `GEMINI_API_KEY` / `LLM_API_KEY`）。**不要**把真实密钥提交进仓库。

启动 UI：

```bash
archium
# 或
streamlit run app.py
```

## 测试

```bash
pytest tests/unit -q
pytest tests/integration -q
pytest tests/golden/mission -v -m regression
pytest tests/golden/regression -v -m regression
```

涉及真实 API 的 Live 评估（默认不进 CI）：

```powershell
$env:ARCHIUM_LIVE_LLM = "1"
python scripts/eval_mission_live.py
```

修改代码后建议至少跑与改动相关的单测；涉及工作流 / Mission / 导出时补跑对应 golden 或 smoke。

## 分支与 PR

1. 从默认分支拉取最新代码并开 topic 分支（例如 `fix/...`、`fix/...`）。
2. 保持改动聚焦；大功能请拆成多个 PR。
3. PR 描述写清：**动机**、**改了什么**、**如何验证**。
4. 若触及用户可见行为，更新相关 `docs/` 或 README 片段。
5. 不要提交：`.env`、密钥、客户原始资料、未脱敏的 golden fixture 文件。

可使用仓库内的 Pull Request 模板填写清单。

## 问题反馈

- Bug / 功能建议：GitHub Issues
- 安全漏洞：**不要**开公开 Issue，见 [SECURITY.md](SECURITY.md)

## 许可

贡献即表示你同意将贡献以 **MIT License** 授权给本项目（与仓库根目录 [LICENSE](LICENSE) 一致）。
