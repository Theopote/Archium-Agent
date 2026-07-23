## 问题 14 已落地

架构文档不再只靠叙述：在 `docs/architecture/current-system.md` 增加了 **机器可读契约锚点**（`arch-contract:*`），并由测试对照运行时代码。

### 契约测试（`tests/unit/test_architecture_contracts.py`）
| 测试 | 校验内容 |
|------|----------|
| capacity statuses | `fits/tight/overloaded/impossible` ≡ `CapacityStatus` |
| comment scopes | 五类作用域 ≡ `ElementCommentScope`（文档已从「四种」更正） |
| image treatment modes | ≡ `ImageTreatmentMode` |
| evidence policy | 图纸/证据图仅允许 `none` / `safe_normalize`，禁止 `presentation_unify` |
| derivative 不可变 | `ImageDerivative` 含 `original_asset_id` / `params_hash` 等 |
| overflow 默认 | `LayoutPlan` 默认 `warn` |
| canvas 能力 | `marquee` / `shiftKey` / `set_studio_selection` 存在于前端与桥接 |
| 产品五段 | `materials→…→deliver` ≡ `primary_stages()` |

`8 passed`。维护约定已写入 `docs/documentation-maintenance.md`：改枚举必须同步锚点并跑该测试。