# 01 — Project foundation

模块：工程骨架 / 打包 / 入口 / CI / 发布文档契约  
前缀：`PF-`  
更新：2026-07-23

| 编号 | 严重级别 | 状态 | 问题 | 文件 | 影响 | 修复方案 | 验收标准 | 提交 SHA |
|------|----------|------|------|------|------|----------|----------|----------|
| PF-001 | P0 | done | Legacy 与主包未隔离，静态检查/导入易混入 | `pyproject.toml`; `legacy/`; `tests/unit/test_legacy_isolation.py` | 主产品边界不清，CI 范围漂移 | Scheme B：主包排除 legacy；测试守卫 | `pytest tests/unit/test_legacy_isolation.py` 绿；ruff/mypy 不含 legacy | `-` |
| PF-002 | P0 | done | `archium` CLI 与 `streamlit run app.py` 双入口环境不一致 | `archium/bootstrap.py`; `app.py`; `archium/cli.py` | `.env`/Settings 加载路径分裂 | 统一 `bootstrap_runtime` / `create_application` | `pytest tests/unit/test_bootstrap.py` 绿 | `-` |
| PF-003 | P1 | done | `full` extra 未覆盖全部 runtime extras | `pyproject.toml`; `tests/unit/test_optional_extras.py` | `pip install .[full]` 装不全 | 守卫断言 full ⊇ 其余 runtime extras | 该单测绿 | `-` |
| PF-004 | P1 | done | 锁文件多工具生成、不可复现 | `requirements/*.lock`; `scripts/compile_requirement_locks.py` | CI/本地漂移 | 仅 uv 编译；文档写明 | 三份 lock 可再生成；CI 从 lock 安装 | `-` |
| PF-005 | P1 | done | Documentation URL 非默认分支 | `pyproject.toml` | 外链 404 | 指向 `.../tree/master/docs` | URL 可访问 | `-` |
| PF-006 | P1 | done | Ruff/mypy 范围与 CI 不一致；Legacy 未冻结声明 | `pyproject.toml`; `tests/unit/test_static_check_scope.py` | 本地绿 CI 红或反向 | 对齐 src/packages；守卫 | `test_static_check_scope` 绿 | `-` |
| PF-007 | P1 | done | CI 单层过重；benchmark 误写 golden | `.github/workflows/ci.yml` | 反馈慢；污染基线 | `compatibility` / `quality-full`；CI materialize ≠ approve-goldens | 工作流分层清晰；benchmark 步无 `--approve-goldens` | `-` |
| PF-008 | P1 | done | 能力完成度仅靠模块测试叙述 | `docs/release-capability-matrix.md`; `docs/user-task-playbooks.md` | 误报 Stable | 发布等级 + 剧本 A–E | `pytest tests/unit/test_release_capability_docs.py` 绿 | `-` |
| PF-009 | P1 | done | 架构文档与代码合同无机器校验 | `docs/architecture/current-system.md`; `tests/unit/test_architecture_contracts.py` | 文档漂移 | `arch-contract:*` 围栏 + 测试 | 合同测试绿 | `-` |
| PF-010 | P2 | accepted-debt | `legacy/` 仍在仓库树内 | `legacy/` | 误用风险 | 保留只读；文档标明 frozen | 隔离测试持续绿；无新 legacy API | `-` |
| PF-011 | P1 | open | Beta 阻断项 B3–B6（golden/CI/smoke）未清 | `docs/v0.2-beta-backlog.md` | 不能打 beta 标签 | 按 backlog 逐项关闭 | B3–B6 勾选完成 | `-` |

## 说明

工程向「问题 1–14」修复已落入 PF-001…PF-009。SHA 待正式提交后回填。
