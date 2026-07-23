## Batch 14 — Security / Config ✅

### P0 已修
1. **Registry drift** — `pptx_structure_mode` / `pptx_chart_export_mode` 已入 `FIELD_DOMAINS`；已跑 `generate_config_docs.py` 同步 `.env.example` + `docs/configuration-reference.md`
2. **URI 路径穿越** — `resolve_under()` 约束 `storage://` / `project://` / `benchmark://`
3. **文件名净化** — `LocalProjectStorage` 仅用 basename + `_assert_under`
4. **Alembic** — `hide_password=True`（避免迁移 URL 泄露密码）

### 测试
`15 passed`（local_storage / asset_path_resolver / config_reference_sync）

### 文档
`docs/architecture/current-system.md`：凭证优先级 + URI 落盘约束 + registry 全覆盖

### Backlog（未修）
| 项 | 说明 |
|---|---|
| `block_export_on_critical_review` 默认 False | 与文档不一致 |
| Studio / asset_reference 绝对路径 | 仍可能写入机器路径 |
| Unsplash 字段文案过时 | 文案/Schema |
| SecretStr 覆盖不全 | 部分密钥字段 |
| multimodal `image_paths` unbound | 配置未绑定 |

---

下一批：**15 Tests / Fixtures**。说 **继续** 即可。