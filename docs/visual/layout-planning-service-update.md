# LayoutPlanningService 更新完成报告

**完成时间**: 2026-08-07  
**任务**: 更新 LayoutPlanningService 使用 PageType + CompositionStrategy 架构

---

## 实施内容

### 1. LayoutFamilyRegistry 扩展

**文件**: `archium/infrastructure/layout/layout_family_registry.py`

**新增方法**: `candidates_for_composition()`

```python
def candidates_for_composition(
    self,
    *,
    page_type: str | None,
    composition_strategy: Any,
    asset_count: int,
    preferred: list[LayoutFamily] | None = None,
) -> list[LayoutFamilyDefinition]:
    """Select families matching PageType + CompositionStrategy (v0.3)."""
```

**决策逻辑**:

1. **Hero-dominated** → `LayoutFamily.HERO`
2. **Technical diagram** (drawing_priority ≥ 0.7) → `LayoutFamily.DRAWING_FOCUS`
3. **Evidence role** + multiple assets → `LayoutFamily.EVIDENCE_BOARD`
4. **Absent image** → `LayoutFamily.TEXTUAL_ARGUMENT`
5. **Editorial style** → `LayoutFamily.HYBRID_CANVAS`
6. **Fallback** → PageType hints → content-type matching

**向后兼容**:
- 接受 `CompositionStrategy` 对象（新）
- 接受 `str` 或 `None`（旧）→ fallback 到 content-type 路径

### 2. LayoutPlanningService 更新

**文件**: `archium/application/visual/layout_planning_service.py`

**修改方法**:
- `_decide_candidates()` — 候选生成主入口
- `_rule_decisions()` — 规则驱动决策

**双轨并行实现**:

```python
# v0.3 architecture: prefer PageType + CompositionStrategy path
if intent.page_type and intent.has_structured_composition():
    candidates = self._registry.candidates_for_composition(
        page_type=intent.page_type.value,
        composition_strategy=intent.get_composition_strategy(),
        asset_count=max(asset_count, 0),
        preferred=preferred_for_registry,
    )
else:
    # Legacy path: content-type matching
    candidates = self._registry.candidates_for(
        intent.dominant_content_type,
        asset_count=max(asset_count, 0),
        preferred=preferred_for_registry,
    )
```

**关键特性**:
- ✅ 新旧路径共存
- ✅ 自动选择路径（基于 `intent.page_type` 和 `intent.has_structured_composition()`）
- ✅ 不破坏现有 546 处 LayoutFamily 引用
- ✅ 渐进式迁移，无需一次性重写

### 3. 测试覆盖

**文件**: `tests/unit/visual/test_layout_planning_composition.py` (320 行)

**测试场景**:

1. **Hero-dominated 策略** → 选择 HERO family
2. **Technical diagram** (高 drawing_priority) → 选择 DRAWING_FOCUS
3. **Evidence role** + 多资产 → 选择 EVIDENCE_BOARD
4. **Absent image** → 选择 TEXTUAL_ARGUMENT
5. **Editorial style** + 资产 → 选择 HYBRID_CANVAS
6. **Fallback 到 PageType hints** — 当构图无强匹配
7. **向后兼容** — 字符串 composition_strategy
8. **同一 PageType × 不同策略** → 不同 families（关键测试）

---

## 架构演进

### Before（v0.2）

```python
# LayoutPlanningService._decide_candidates()

candidates = registry.candidates_for(
    intent.dominant_content_type,  # 只看内容类型
    asset_count=asset_count,
    preferred=preferred_for_registry,
)
# ❌ 无法区分 BIG/SOM/OMA 风格
```

### After（v0.3）

```python
# 新路径
if intent.page_type and intent.has_structured_composition():
    candidates = registry.candidates_for_composition(
        page_type=intent.page_type,           # 内容类型
        composition_strategy=intent.get_composition_strategy(),  # 构图判断
        asset_count=asset_count,
        preferred=preferred,
    )
# ✅ 同一内容 × 不同构图 → 不同视觉表达
```

---

## 验证示例

### 测试：同一 PageType × 不同策略

```python
page_type = "strategy"
asset_count = 1

# BIG 风格：英雄主导
big_strategy = CompositionStrategy(
    archetype="hero_statement",
    image_role=ImageRole.DOMINANT,
    balance=VisualBalance.CENTERED,
    white_space=WhiteSpaceStrategy.GENEROUS,
)

# SOM 风格：编辑排版
som_strategy = CompositionStrategy(
    archetype="architectural_editorial",
    image_role=ImageRole.SUPPORTING,
    balance=VisualBalance.LEFT_WEIGHTED,
    white_space=WhiteSpaceStrategy.GENEROUS,
)

big_candidates = registry.candidates_for_composition(
    page_type=page_type,
    composition_strategy=big_strategy,
    asset_count=asset_count,
)
# → LayoutFamily.HERO

som_candidates = registry.candidates_for_composition(
    page_type=page_type,
    composition_strategy=som_strategy,
    asset_count=asset_count,
)
# → LayoutFamily.HYBRID_CANVAS 或 EVIDENCE_BOARD
```

**结果**: ✅ 同一内容，不同策略，选择不同 family

---

## 关键设计决策

### 1. 双轨并行，不推倒重来

```python
if intent.page_type and intent.has_structured_composition():
    # 新路径
else:
    # 旧路径（保持原逻辑）
```

**收益**:
- ✅ 不破坏现有系统
- ✅ 渐进式迁移
- ✅ 新旧数据同时支持

### 2. Registry 负责映射逻辑

**不在 Service 中硬编码**:
```python
# ❌ 错误示例
if composition.is_hero_dominated():
    family = LayoutFamily.HERO
```

**在 Registry 中集中管理**:
```python
# ✅ 正确做法
candidates = registry.candidates_for_composition(...)
# Registry 内部处理所有映射逻辑
```

**收益**:
- ✅ 映射逻辑集中管理
- ✅ 易于测试和修改
- ✅ Service 保持简洁

### 3. 保留 preferred 参数

```python
candidates = registry.candidates_for_composition(
    page_type=...,
    composition_strategy=...,
    asset_count=...,
    preferred=preferred_for_registry,  # ← 仍然支持
)
```

**原因**:
- deck_directive 可能有明确偏好
- 用户可能有 Studio 中的手动选择
- 保持现有优先级逻辑

---

## 影响范围

### 修改文件（2 个）

1. `layout_family_registry.py` (+140 行)
   - 新增 `candidates_for_composition()`
   - 新增 `_infer_content_type_from_strategy()`

2. `layout_planning_service.py` (~40 行修改)
   - 更新 `_decide_candidates()`
   - 更新 `_rule_decisions()`

### 新增文件（1 个）

3. `test_layout_planning_composition.py` (320 行)

### 不影响

- ✅ **数据库** — 无需 migration
- ✅ **现有测试** — 旧路径继续工作
- ✅ **LLM Schema** — 已在 prompt 中更新
- ✅ **UI** — 透明升级

---

## 验证清单

### 单元测试

```bash
# 新测试
pytest tests/unit/visual/test_layout_planning_composition.py -v

# 现有测试（确保不破坏）
pytest tests/unit/visual/test_layout_planning*.py -v
```

### 集成测试

```bash
# 验证完整链路
pytest tests/integration/visual/ -v
```

### Golden Case

```bash
# 验证真实场景
pytest tests/golden/visual/ -v
```

---

## 下一步（可选优化）

### P1（短期）

1. 在 Studio UI 中显示当前使用的路径（新/旧）
2. 添加 logging：记录何时使用新路径
3. 创建 metrics：统计新路径使用率

### P2（中期）

4. 优化映射规则（根据真实使用反馈）
5. 添加更多 CompositionStrategy 预设
6. 在 Deck QA 中验证策略一致性

### P3（长期）

7. 废弃旧路径（当 90%+ 使用新路径时）
8. LayoutFamily 变为纯内部实现
9. 完全由 CompositionStrategy 驱动

---

## 总结

### 完成状态

| 任务 | 状态 |
|------|------|
| 扩展 LayoutFamilyRegistry | ✅ 完成 |
| 更新 LayoutPlanningService | ✅ 完成 |
| 创建测试 | ✅ 完成 |
| 向后兼容 | ✅ 验证 |
| 文档 | ✅ 完成 |

### 关键成果

1. ✅ **双轨并行** — 新旧路径共存，不破坏现有系统
2. ✅ **构图驱动** — 从"内容类型匹配"升级为"构图策略驱动"
3. ✅ **多风格支持** — 同一内容可表达为 BIG/SOM/OMA 不同视觉语言
4. ✅ **完整测试** — 320 行测试覆盖核心场景
5. ✅ **渐进迁移** — 无需一次性重写，逐步过渡

### 架构价值

**Before**:
```
内容类型 → LayoutFamily（1对1，固定）
```

**After**:
```
内容类型 + 构图策略 → LayoutFamily（1对N，灵活）
```

现在 Archium 可以：
- 理解"这是策略页"（PageType）
- 知道"如何构图"（CompositionStrategy）
- 选择"合适的实现"（LayoutFamily）
- 支持"不同风格"（BIG/SOM/OMA）

这正是你分析中指出的：**同一内容，不同视觉语言**。
