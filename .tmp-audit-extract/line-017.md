同意：下一阶段应以收敛为主。第一批「问题 1」已按**方案 B**落地隔离。

## 验收

`archium` 内 `from legacy|import legacy`：**空**（已用 `tests/unit/test_legacy_isolation.py` 锁住）。

## 已做

| 动作 | 结果 |
|------|------|
| 切断硬依赖 | `command_center.py` 改为退役页，不再加载 `legacy` |
| 方案 B 打包 | `include = ["archium*"]`；移除 `archium-legacy` 脚本 |
| 工具链 | mypy/ruff 不再把 `legacy` 当主包 |
| UI | 系统诊断去掉「Legacy 快速 PPT」 |
| 文档 | README + `docs/architecture/current-system.md` 改为仓库内按需运行 |

Legacy 运行方式（仅检出）：

```bash
python -m legacy.main
# 或
python main.py
```

## 仍须知情（未删）

- `legacy/` 源码与根 shim 仍在仓库；**反向** `legacy → archium`（LLM）仍存在——方向正确，主产品不依赖遗留。
- `tests/unit/test_router_integration.py` 仍测 legacy（合理）。
- 名称含 “legacy” 的域内兼容层（如 `export_presentation_pptx_legacy`）是主链历史 API，**不是** `legacy/` 包。

## 批次 1 其余观察（未改）

正式入口清晰（`archium` / `app.py`）；测试分层与 CI 复杂度高但可用；文档与代码在入口上已对齐。下一刀更适合进 **批次 2 Domain**（模型重复 / 枚举 / 跨层依赖），或继续扫批次 1 的 CI/依赖细节。

需要的话我可以直接开批次 2，或先提交本轮 Legacy 隔离变更。

[REDACTED]