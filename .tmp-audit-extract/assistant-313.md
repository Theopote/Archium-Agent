## 问题 6–7：采用「Legacy 冻结」并与 CI 对齐

配置侧其实已基本到位；本轮补齐守卫、文档，并修掉当前会挡 CI 的 mypy 错误。

### 问题 6（配置 vs CI）
**选择：Legacy 冻结，不检查。**

| 工具 | 配置 | CI |
|---|---|---|
| Ruff | `src = ["archium", "tests"]` | `ruff check archium tests` |
| Mypy | `packages = ["archium"]` | `mypy archium` |

- README / `current-system.md` 写明：**Legacy 冻结、不接功能修改、静态检查不覆盖**
- 新增 `tests/unit/test_static_check_scope.py`，防止再漂回「配置写 legacy、CI 不跑」

### 问题 7（`ignore_missing_imports`）
已是：

- 全局 `ignore_missing_imports = false`
- 仅对 `streamlit` / `fitz` / `chromadb` 等无 stub 包做 overrides
- `domain` / `application` 显式保留严格标志

### 顺带修复（mypy 现 0 错误）
- `RenderNode` 列表不变性（2 处）
- `scene_pptx` 的 `reason: str | None` 赋值
- `project_sidebar` 的 `defaults` 注解

`mypy archium`：`Success: no issues found in 651 source files`；scope 测试 `3 passed`。