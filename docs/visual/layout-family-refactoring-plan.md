# LayoutFamily 架构问题分析与解决方案

## 问题诊断

### 当前架构（有问题）

```
LayoutFamily = PageType + VisualStyle（耦合）
```

**示例：**
```python
LayoutFamily.HERO = "英雄页" + "满幅出血风格"
LayoutFamily.EVIDENCE_BOARD = "证据页" + "网格排列风格"
```

**问题：**
同一个内容类型（例如"策略页"），不同事务所的视觉表达完全不同：

| 事务所 | 同一个"策略页"的表达 |
|--------|---------------------|
| **BIG** | 巨大图片 + 大胆字体 + 强烈颜色 |
| **SOM** | 严格网格 + 大量留白 + 技术感 |
| **OMA** | 冲突拼贴 + 信息密度 + 实验性 |

当前的 `LayoutFamily.STRATEGY_CARDS` 只能表达**一种**固定风格，无法适应不同视觉语言。

### 根本原因

`LayoutFamily` 同时承担了三个职责：

1. **内容类型识别**（PageType）— "这是什么内容？"
2. **构图策略**（CompositionStrategy）— "如何组织视觉元素？"
3. **视觉风格**（StylePreset）— "采用什么视觉语言？"

这导致组合爆炸：
```
10 PageTypes × 5 CompositionStrategies × 3 StylePresets = 150 LayoutFamilies！
```

### 使用情况统计

- **546 处引用** across 49 files
- 核心使用场景：
  1. `LayoutFamilyRegistry` — 定义和查询
  2. `LayoutPlanningService` — 候选选择（92 次）
  3. Layout generators — 10 个 family-specific generators
  4. `DeckCompositionService` — 节奏分配（23 次）
  5. Visual services — 意图生成、QA、修复

---

## 目标架构（正确）

```
PageType（内容）+ CompositionStrategy（构图）+ StylePreset（风格）
```

### 三层分离

| 层 | 职责 | 示例 | 数量 |
|----|------|------|------|
| **PageType** | 内容类型 | SITE_ANALYSIS, STRATEGY, EVIDENCE | ~15 |
| **CompositionStrategy** | 构图判断 | hero_dominated, editorial, technical | ~10 |
| **StylePreset** | 视觉风格 | BIG_bold, SOM_minimal, OMA_collage | ~5 |

### 组合示例

同一个 `PageType.STRATEGY`：

```python
# BIG 风格
PageType.STRATEGY + CompositionStrategy(hero_dominated) + StylePreset.BIG_BOLD
→ 巨大图片、动态张力、强烈色彩

# SOM 风格  
PageType.STRATEGY + CompositionStrategy(editorial) + StylePreset.SOM_MINIMAL
→ 网格系统、大量留白、技术字体

# OMA 风格
PageType.STRATEGY + CompositionStrategy(collage) + StylePreset.OMA_EXPERIMENTAL
→ 拼贴、高密度、冲突张力
```

---

## 迁移路径（分三阶段）

### Phase 1: 引入 PageType（不破坏现有）

**新增模型：**
```python
class PageType(StrEnum):
    """Pure content classification — decoupled from visual style."""
    COVER = "cover"
    SECTION_OPENER = "section_opener"
    SITE_ANALYSIS = "site_analysis"
    STRATEGY = "strategy"
    EVIDENCE = "evidence"
    COMPARISON = "comparison"
    PROCESS = "process"
    TECHNICAL_DRAWING = "technical_drawing"
    DATA_METRICS = "data_metrics"
    TEXT_ARGUMENT = "text_argument"
    MIXED_CONTENT = "mixed_content"
```

**在 VisualIntent 中添加：**
```python
class VisualIntent:
    # 新增（不替代 preferred_layout_families）
    page_type: PageType | None = None
    composition_strategy: CompositionStrategy | str | None = None
    style_preset_id: str | None = None  # "BIG_bold", "SOM_minimal", etc.
    
    # 保留向后兼容
    preferred_layout_families: list[LayoutFamily] = Field(default_factory=list)
```

**映射关系：**
```python
# PageType → LayoutFamily 的兼容映射
PAGE_TYPE_TO_LAYOUT_FAMILY_HINTS: dict[PageType, list[LayoutFamily]] = {
    PageType.COVER: [LayoutFamily.HERO, LayoutFamily.TEXTUAL_ARGUMENT],
    PageType.STRATEGY: [LayoutFamily.STRATEGY_CARDS, LayoutFamily.TEXTUAL_ARGUMENT],
    PageType.EVIDENCE: [LayoutFamily.EVIDENCE_BOARD, LayoutFamily.COMPARATIVE_MATRIX],
    # ...
}
```

### Phase 2: 增强 LayoutFamilyRegistry（读取 CompositionStrategy）

**新增方法：**
```python
class LayoutFamilyRegistry:
    def candidates_for_composition(
        self,
        page_type: PageType,
        composition_strategy: CompositionStrategy,
        asset_count: int,
    ) -> list[LayoutFamilyDefinition]:
        """Select families matching page type + composition strategy."""
        
        # 1. 根据 PageType 缩小范围
        page_hints = PAGE_TYPE_TO_LAYOUT_FAMILY_HINTS.get(page_type, [])
        
        # 2. 根据 CompositionStrategy 特征匹配
        if composition_strategy.is_hero_dominated():
            return [self.get(LayoutFamily.HERO)]
        
        if composition_strategy.image_role == ImageRole.EVIDENCE:
            if composition_strategy.drawing_priority > 0.7:
                return [self.get(LayoutFamily.DRAWING_FOCUS)]
            else:
                return [self.get(LayoutFamily.EVIDENCE_BOARD)]
        
        # 3. Fallback 到现有逻辑
        content_type = self._infer_content_type(page_type)
        return self.candidates_for(content_type, asset_count=asset_count)
```

### Phase 3: 独立 Layout Generators（不依赖 LayoutFamily）

**长期目标：**
```python
# 不再是 family-specific generators
# archium/infrastructure/layout/generators/hero.py  ❌

# 而是 composition-driven generators
# archium/infrastructure/layout/generators/composition_executor.py  ✅

class CompositionExecutor:
    def generate_layout(
        self,
        page_type: PageType,
        composition: CompositionStrategy,
        design_system: DesignSystem,
        content: SlideSpec,
    ) -> LayoutPlan:
        """Execute composition strategy → LayoutPlan."""
        
        # 根据 composition.archetype 选择执行策略
        if composition.is_hero_dominated():
            return self._generate_hero_layout(...)
        elif composition.is_editorial_style():
            return self._generate_editorial_layout(...)
        elif composition.is_technical_diagram():
            return self._generate_technical_layout(...)
```

---

## 实施优先级

### P0（本次实现）
1. ✅ 创建 `CompositionStrategy` 模型（已完成）
2. ⏭ 创建 `PageType` 枚举
3. ⏭ 在 `VisualIntent` 中添加 `page_type`（不删除 `preferred_layout_families`）
4. ⏭ 更新 `LayoutPlanningService` 读取 `CompositionStrategy`

### P1（短期）
5. 在 `LayoutFamilyRegistry` 添加 `candidates_for_composition()` 方法
6. 创建 `PAGE_TYPE_TO_LAYOUT_FAMILY_HINTS` 映射
7. 更新 prompt 生成 `page_type + composition_strategy`

### P2（中期）
8. 创建 `StylePreset` 系统（BIG/SOM/OMA 等）
9. 在 `ArtDirection` 中绑定 `style_preset_id`
10. 让 `DesignSystem` 可以叠加 `StylePreset` 修改

### P3（长期）
11. 重构 layout generators 为 composition-driven
12. 逐步废弃 family-specific generators
13. `LayoutFamily` 变为内部实现细节（不暴露给 LLM）

---

## 向后兼容策略

### 策略 1: 双轨并行（推荐）

```python
# LayoutPlanningService.generate_candidates()

if intent.page_type and intent.has_structured_composition():
    # 新路径：PageType + CompositionStrategy
    candidates = registry.candidates_for_composition(
        page_type=intent.page_type,
        composition_strategy=intent.get_composition_strategy(),
        asset_count=len(assets),
    )
else:
    # 旧路径：LayoutFamily（保持原有逻辑）
    candidates = registry.candidates_for(
        content_type=intent.dominant_content_type,
        asset_count=len(assets),
        preferred=intent.preferred_layout_families,
    )
```

### 策略 2: 自动填充

```python
# 如果只有 LayoutFamily，自动推断 PageType
if not intent.page_type and intent.preferred_layout_families:
    intent.page_type = infer_page_type_from_family(
        intent.preferred_layout_families[0]
    )
```

---

## 数据库影响

**无需 migration！**

因为：
1. `VisualIntent` 的新字段都是可选（`| None`）
2. 现有 JSON 字段可以直接扩展
3. `composition_strategy` 已经从 `str` 升级为 `CompositionStrategy | str`

---

## Golden Case 验证

### 测试场景：同一内容 × 不同风格

```python
# 同一个 SlideSpec（策略页）
spec = SlideSpec(
    layout="strategy",
    title="设计策略",
    lead_statement="三大原则...",
    body_text=["原则一：...", "原则二：...", "原则三：..."],
)

# 测试 1: BIG 风格
intent_big = VisualIntent(
    page_type=PageType.STRATEGY,
    composition_strategy=CompositionStrategy(
        archetype="hero_statement",
        image_role=ImageRole.DOMINANT,
        balance=VisualBalance.CENTERED,
        white_space=WhiteSpaceStrategy.GENEROUS,
    ),
    style_preset_id="BIG_bold",
)
# → 预期：大图、动态、强烈

# 测试 2: SOM 风格
intent_som = VisualIntent(
    page_type=PageType.STRATEGY,
    composition_strategy=CompositionStrategy(
        archetype="architectural_editorial",
        image_role=ImageRole.SUPPORTING,
        balance=VisualBalance.LEFT_WEIGHTED,
        white_space=WhiteSpaceStrategy.GENEROUS,
    ),
    style_preset_id="SOM_minimal",
)
# → 预期：网格、留白、技术

# 验证：两个 LayoutPlan 应该明显不同
assert layout_big.hero_element_id != layout_som.hero_element_id
assert layout_big.whitespace_ratio > layout_som.whitespace_ratio
```

---

## 总结

### 核心原则
1. **内容 ≠ 风格** — 同一内容可以有多种视觉表达
2. **不推倒重来** — 双轨并行，保持兼容
3. **渐进迁移** — 分三阶段，每阶段都可用

### 关键收益
- ✅ 支持多种视觉语言（BIG/SOM/OMA）
- ✅ 组合数从 150 降到 15 × 10 × 5（可管理）
- ✅ LLM 只需理解内容，不需记住"模板"
- ✅ 向后兼容，不破坏现有系统

### 下一步
立即实现 P0：
1. 创建 `PageType` 枚举
2. 升级 `VisualIntent`
3. 更新 `LayoutPlanningService` 读取逻辑
