# 14 — Tests / security / config

模块：测试分层、配置注册、依赖安全  
前缀：`TS-`  
更新：2026-07-23

| 编号 | 严重级别 | 状态 | 问题 | 文件 | 影响 | 修复方案 | 验收标准 | 提交 SHA |
|------|----------|------|------|------|------|----------|----------|----------|
| TS-001 | P0 | done | Settings 新字段未进 `FIELD_DOMAINS`；配置文档过期 | `archium/config/registry.py`; docs generators | 生成器/同步测试失败 | 注册 + 再生 docs | 配置生成测试绿 | `-` |
| TS-002 | P0 | done | 资源 URI 越狱；上传文件名未净化 | `asset_path_resolver`; `local_storage` | 路径穿越 | jail + sanitize | 安全单测绿 | `-` |
| TS-003 | P0 | done | Alembic 日志暴露密码 | alembic env | 凭据泄漏 | `hide_password` | 日志无明文密码 | `-` |
| TS-004 | P0 | done | domain/spike 测试档位错；门禁图内联 | `tests/conftest.py` 等 | CI 档混乱 | 归 unit；fixture 化 | tier marker 测试绿 | `-` |
| TS-005 | P1 | open | export 阻断默认、绝对路径、SecretStr 缺口、多模态未绑定 | config / settings | 配置不安全或不一致 | 逐项收紧 + 文档 | Batch 14 backlog 清零 | `-` |
| TS-006 | P2 | open | 重复 fixtures/markers；calibration 臃肿；output(s) 命名 | tests | 维护成本 | 去重规范 | 无重复 marker 定义 | `-` |
| TS-007 | P1 | done | 剧本 A 无可重复自动门禁命令 | `scripts/run_playbook_a_gate.py`; playbooks | 发版无固定命令 | 脚本 + 文档 + 守卫 | `test_playbook_a_documents_repeatable_gate_script` 绿 | `-` |
| TS-008 | P1 | mitigated | chromadb CVE-2026-45829 无修复版 | `docs/security/dependency-allowlist.json` | 审计红；理论 RCE（HTTP 服务） | allowlist 至 2026-10-01；仅 PersistentClient | `ci_security_audit_gate true pip` 清洁锁环境绿；到期前升级 | `-` |
| TS-009 | P1 | open | 分支保护未要求 security audit；enforce 未提前开 | `.github/workflows/ci.yml`; triage | Aug 8 突然变红或无人看 | 保护规则 + 可选提前 enforce | triage checklist 剩余项勾完 | `-` |
| TS-010 | P0 | open | 非开发者剧本 A + 修改成本（Beta B10） | playbooks; rehearsal tooling | 不能宣称 beta 可用 | 工具链就绪（`new_beta_session` + meta + summarize）；**待真人 session 数据** | B10 关闭；有 session 记录 | `-` |
| TS-011 | P1 | done | setuptools CVE：CI/build 未钉补丁版 | `pyproject.toml`; ci security-scan | 构建链漏洞 | `setuptools>=83` | security-scan 安装步骤含 pin | `-` |
| TS-012 | P2 | open | 开发机 torch 等非 lock 包污染本地 audit | 本地 env | 误报 | 清洁 venv 审计；勿 allowlist torch | 文档已说明；CI 无 torch | `-` |
