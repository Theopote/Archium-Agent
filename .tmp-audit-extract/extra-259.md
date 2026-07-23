## Batch 15 — Tests / Fixtures ✅

### P0 已修
1. **CI 分层断链** — `tests/domain/`、`tests/spike/` 纳入 `_TIER_PATH_PREFIXES` → `unit`；`pytest -m unit` 现多收集约 28 条（此前为 0）
2. **Gate fixture 耦合** — `sample_image_file` 改为 `materialize_inline_image`，不再依赖 calibration 语料路径
3. **Marker 漂移** — `pyproject.toml` 对齐 application→integration、domain/spike→unit；补齐 `regression` / `fixture_acceptance` / `live_llm`；golden `conftest` 去掉与 toolchain 冲突的 `smoke` 重定义

### 测试
`52 passed`（tier markers + domain + spike + e2e benchmark 非全链路）

### 文档
`docs/architecture/current-system.md` 增加「测试分层」表

### Backlog（未修）
| 项 | 说明 |
|---|---|
| 重复 fixture | `test_e2e_benchmark_service` 本地再定义 `mock_llm` / `sample_*` |
| e2e `conftest` 重复注册 marker | 与 pyproject 重复，可收敛 |
| calibration 语料体积 | 可选语料仍进仓库；与 gate 已解耦 |
| `output` vs `outputs` 命名 | Phase 7 目录并存 |

---

下一批：**16 文档与删除阶段**。说 **继续** 即可。