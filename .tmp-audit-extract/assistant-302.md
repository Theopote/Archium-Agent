## 问题 3–5 已处理

### 问题 3：`full` Extra 漂移
- 新增 `tests/unit/test_optional_extras.py`：`ui|documents|workflow|vector|llm|postgres` ⊆ `full`（按 requirement 归一化比较）
- `2 passed`

### 问题 4：锁定依赖
- 选定 **uv**（不并行维护 Poetry/pip-tools）
- `requirements/base.lock`、`full-py311.lock`、`full-py312.lock` + `requirements/README.md`
- 再生脚本：`python scripts/compile_requirement_locks.py`
- CI 主流程改为 `pip install -r requirements/full-py*.lock` + `.[dev]` constraint
- `Dockerfile.all-in-one` 改为用 `full-py311.lock`（顺带修掉不存在的 `render` extra）

### 问题 5：文档 URL 分支
- `Documentation` → `.../tree/master/docs`（默认分支保持 `master`，未改成 `main`）
- 测试守卫防止再指回 `main`

开发者仍可用 `pip install -e ".[full,dev]"`；Docker/CI/发布候选优先锁文件。未提交。