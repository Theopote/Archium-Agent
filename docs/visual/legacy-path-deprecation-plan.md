# Legacy Path Deprecation Plan — v0.3 → v1.0

**目标**: 完全废弃 content-type 路径，LayoutFamily 变为纯内部实现  
**时间线**: 渐进式，基于真实使用数据  
**触发条件**: 90%+ 使用 composition-driven 路径

---

## 当前状态（v0.3）

### 双轨并行架构

```python
# LayoutPlanningService._decide_candidates()

if intent.page_type and intent.has_structured_composition():
    # 新路径（v0.3）
    candidates = registry.candidates_for_composition(
        page_type=intent.page_type,
        composition_strategy=intent.get_composition_strategy(),
        asset_count=asset_count,
    )
else:
    # 旧路径（legacy）
    candidates = registry.candidates_for(
        intent.dominant_content_type,
        asset_count=asset_count,
        preferred=preferred,
    )
```

### 问题

1. **维护负担** — 两套路径需要同时维护
2. **复杂度** — 新用户难以理解为什么有两条路径
3. **性能** — 条件判断开销
4. **LLM 输出** — 仍需生成 `preferred_layout_families` 以兼容

---

## 目标架构（v1.0）

### 单一路径：Composition-Driven

```python
# v1.0 simplified architecture

candidates = registry.candidates_for_composition(
    page_type=intent.page_type,  # 必需
    composition_strategy=intent.get_composition_strategy(),  # 必需
    asset_count=asset_count,
)
# ✅ 只有一条路径
# ✅ LayoutFamily 是内部实现细节
# ✅ LLM 不再需要知道 LayoutFamily
```

### LayoutFamily 的未来角色

```python
# v1.0: LayoutFamily 变为纯实现细节

class LayoutFamilyDefinition:
    """Internal implementation detail — not exposed to LLM or UI."""
    family: LayoutFamily
    # ... 内部字段
```

**不再暴露给**:
- ❌ LLM prompts（不需要输出 `preferred_layout_families`）
- ❌ VisualIntent（`preferred_layout_families` 字段废弃）
- ❌ 用户 UI（用户选择 PageType + 风格，不选 Family）

**仅用于**:
- ✅ Registry 内部映射
- ✅ Generator 实现
- ✅ 调试和日志

---

## 分阶段废弃计划

### Phase 1: 监控（当前）✅

**目标**: 了解新旧路径使用情况

**实施**:
- ✅ `LayoutPlanningMetrics` 系统
- ✅ 记录每次路径选择
- ✅ 聚合统计

**输出**:
```python
summary = get_layout_planning_summary()
# {
#   "total_operations": 1000,
#   "composition_driven_count": 750,
#   "content_type_legacy_count": 250,
#   "composition_driven_percentage": 75.0,
#   "ready_for_deprecation_90pct": False
# }
```

**持续时间**: 2-4 周（收集真实使用数据）

---

### Phase 2: 迁移（准备就绪）✅

**目标**: 将现有数据迁移到新架构

**实施**:
- ✅ `VisualIntentMigrationService`
- ✅ 自动推断 `page_type` + `composition_strategy`

**执行**:
```python
# 迁移所有现有 VisualIntent
migrator = VisualIntentMigrationService(session)
migrated, skipped = migrator.migrate_all_intents(dry_run=False)

# 或按 presentation 迁移
migrated, skipped = migrator.migrate_by_presentation(
    presentation_id=UUID("..."),
    dry_run=False,
)
```

**触发条件**: Phase 1 数据显示 >50% 使用新路径

**持续时间**: 1 周（批量迁移 + 验证）

---

### Phase 3: Soft Deprecation（60-80% 使用率）

**目标**: 标记旧路径为废弃，但保持功能

**实施**:

1. **添加废弃警告**:
```python
# LayoutPlanningService._decide_candidates()

if not (intent.page_type and intent.has_structured_composition()):
    # Legacy path
    logger.warning(
        "Using deprecated content-type path. "
        "Please populate page_type and composition_strategy. "
        "This path will be removed in v1.0.",
        extra={
            "deprecation": "LAYOUT_PLANNING.LEGACY_PATH",
            "slide_id": str(slide.id),
        },
    )
    candidates = registry.candidates_for(...)  # 仍然工作
```

2. **更新文档**:
   - 标记 `preferred_layout_families` 为 `@deprecated`
   - 更新所有示例使用新路径
   - 添加迁移指南

3. **UI 提示**:
   - Studio 中显示 "Using legacy path" 警告
   - 提供"自动迁移"按钮

**触发条件**: 60-80% 使用新路径

**持续时间**: 4-8 周（给用户时间适应）

---

### Phase 4: Hard Deprecation（80-90% 使用率）

**目标**: 移除旧路径代码，强制使用新路径

**实施**:

1. **移除旧路径**:
```python
# v1.0-rc: 只保留新路径

def _decide_candidates(...) -> list[LayoutDecisionDraft]:
    # v1.0: 强制要求 page_type + composition_strategy
    if not intent.page_type:
        raise ValueError(
            "VisualIntent.page_type is required in v1.0. "
            "Run migration tool to update existing data."
        )
    
    if not intent.has_structured_composition():
        raise ValueError(
            "VisualIntent.composition_strategy (structured) is required in v1.0. "
            "Run migration tool to update existing data."
        )
    
    candidates = registry.candidates_for_composition(...)
    # ✅ 只有一条路径
```

2. **清理代码**:
   - 删除 `registry.candidates_for(content_type, ...)` 旧方法
   - 删除 `VisualIntent.preferred_layout_families` 字段
   - 删除 LLM prompt 中的 `preferred_layout_families` 生成

3. **数据库清理**:
   - `preferred_layout_families` 列设为 nullable/废弃
   - 不需要 migration（向后兼容）

**触发条件**: 90%+ 使用新路径

**持续时间**: 2 周（RC 测试）

---

### Phase 5: v1.0 Release（完成）

**目标**: 正式发布 v1.0，完全移除旧路径

**架构变化**:

```python
# v1.0 final architecture

# VisualIntent: 只有新字段
class VisualIntent:
    page_type: PageType  # 必需（不再可选）
    composition_strategy: CompositionStrategy  # 必需（不再接受 str）
    # ❌ 删除: preferred_layout_families

# LayoutFamilyRegistry: 只有新方法
class LayoutFamilyRegistry:
    def candidates_for_composition(...) -> list[...]:
        """唯一公开方法"""
    
    # ❌ 删除: candidates_for(content_type, ...)

# LLM Schema: 简化
class VisualIntentDraft:
    page_type: str  # 必需
    composition_strategy: dict  # 必需，结构化对象
    # ❌ 删除: preferred_layout_families
```

**LayoutFamily 角色**:
- ✅ 变为纯内部实现（枚举保留）
- ✅ 不暴露给 LLM/UI
- ✅ 仅在 Registry 和 Generator 内部使用

**触发条件**: Phase 4 成功，95%+ 使用新路径

**持续时间**: 发布后持续监控

---

## 决策矩阵

| 使用率阈值 | Phase | 动作 | 旧路径状态 |
|-----------|-------|------|-----------|
| 0-50% | Phase 1 | 监控 | ✅ 正常工作 |
| 50-60% | Phase 2 | 批量迁移 | ✅ 正常工作 |
| 60-80% | Phase 3 | Soft deprecation | ⚠️ 警告，仍工作 |
| 80-90% | Phase 4 | Hard deprecation | ❌ 抛出异常 |
| 90%+ | Phase 5 | 删除代码 | ❌ 已删除 |

---

## 回滚策略

### 如果新路径出现问题

**Phase 3 之前**:
- ✅ 简单：注释掉新路径，恢复旧路径
- ✅ 无数据损失（旧字段仍在）

**Phase 3-4**:
- ⚠️ 需要保留旧路径代码（作为 feature flag）
- ⚠️ 可以临时禁用废弃警告

**Phase 5 之后**:
- ❌ 无法回滚（代码已删除）
- ❌ 必须修复新路径问题

**因此**: Phase 4 → Phase 5 之间至少保留 4 周缓冲期

---

## 验证清单

### Phase 1 → Phase 2（数据驱动）

- [ ] 收集至少 1000 次真实操作数据
- [ ] 新路径使用率 >50%
- [ ] 新路径错误率 <5%
- [ ] 性能无明显退化

### Phase 2 → Phase 3（迁移完成）

- [ ] 所有现有 VisualIntent 已迁移
- [ ] 迁移准确率 >95%（人工抽查）
- [ ] 旧 deck 重新生成后质量无下降

### Phase 3 → Phase 4（用户适应）

- [ ] 新路径使用率 >80%
- [ ] 用户反馈无重大问题
- [ ] 文档和示例全部更新

### Phase 4 → Phase 5（稳定性验证）

- [ ] RC 版本运行 2 周无严重问题
- [ ] 新路径使用率 >95%
- [ ] 回归测试全部通过

---

## 风险与缓解

### 风险 1: 新路径质量问题

**缓解**:
- Phase 1-2 充分监控
- 保留旧路径作为 fallback（Phase 3）
- 渐进式推进，不激进

### 风险 2: 用户抵制迁移

**缓解**:
- 提供自动迁移工具
- 清晰的文档和示例
- 足够长的 soft deprecation 期（Phase 3）

### 风险 3: 数据迁移不准确

**缓解**:
- 先 dry_run 验证
- 人工抽查迁移结果
- 提供手动修正工具

---

## 监控指标

### 关键指标

1. **新路径使用率**:
   ```
   composition_driven_percentage = 
       composition_driven_count / total_operations * 100
   ```

2. **错误率**:
   ```
   error_rate = error_count / total_operations * 100
   ```

3. **性能**:
   - 平均候选生成时间
   - P95 延迟

### 告警阈值

- ❌ **阻断**: 错误率 >10%
- ⚠️ **警告**: 错误率 >5%
- ⚠️ **警告**: P95 延迟增加 >50%

---

## 总结

### 为什么要废弃旧路径？

1. **简化架构** — 从双轨变为单轨
2. **降低维护成本** — 只维护一套逻辑
3. **提升可理解性** — 新用户不困惑
4. **支持多风格** — 旧路径无法支持 BIG/SOM/OMA
5. **LLM 友好** — 不需要记忆 LayoutFamily 枚举

### 为什么采用渐进式？

1. **降低风险** — 分阶段验证
2. **数据驱动** — 基于真实使用率决策
3. **用户友好** — 给予充分适应时间
4. **可回滚** — Phase 4 之前可以回退

### 最终状态（v1.0）

```
PageType（内容）+ CompositionStrategy（构图）+ StylePreset（风格）
↓
LayoutFamily（内部实现）
↓
LayoutPlan（几何）
```

✅ **LayoutFamily 变为纯内部实现细节**  
✅ **完全由 CompositionStrategy 驱动**  
✅ **支持多种视觉语言（BIG/SOM/OMA）**
