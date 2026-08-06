# Composition Strategy Implementation Summary

## 完成时间
2026-08-07

## 背景

Archium 当前的核心问题是：
- **大脑优秀**（内容理解、策略生成）：★★★★★
- **视觉表达缺乏建筑师认可**：★★☆☆☆

具体表现为：`VisualIntent.composition_strategy` 只是字符串描述，不是结构化的设计判断系统。

## 实施内容

### 1. 核心模型 (`archium/domain/visual/composition_strategy.py`)

创建了完整的结构化构图策略模型，包括：

**核心枚举类型：**
- `CompositionAxis` — 主导轴线（水平/垂直/对角/放射/无）
- `VisualTension` — 视觉张力（对称/非对称/动态/静态）
- `VisualBalance` — 重心分布（居中/左重/右重/上重/下锚）
- `ReadingPathType` — 阅读路径（线性/Z型/F型/放射/层次）
- `WhiteSpaceStrategy` — 留白策略（慷慨/平衡/紧凑/战略性）
- `ImageRole` — 图像角色（主导/支撑/环境/证据/无）
- `TypographyRole` — 文字角色（英雄/编辑/数据标注/叙事/极简）
- `LayeringStrategy` — 层次策略（平面/微深度/强深度）
- `MarginsStrategy` — 边距策略（慷慨/标准/紧凑/非对称）

**CompositionStrategy 模型字段：**
- 设计原型识别：`archetype`
- 构图结构：`dominant_axis`, `focal_point`, `visual_hierarchy`, `reading_path`
- 视觉力量：`tension`, `balance`, `rhythm`
- 元素角色：`image_role`, `typography_role`, `diagram_role`
- 空间策略：`white_space`, `margins`, `layering`
- 建筑特定：`drawing_priority`, `precision_level`, `annotation_density`

**辅助方法：**
- `is_hero_dominated()` — 判断是否英雄图主导
- `is_editorial_style()` — 判断是否编辑风格
- `is_technical_diagram()` — 判断是否技术图纸
- `is_spacious()` — 判断是否宽松布局

**预设原型（5个）：**
1. `architectural_editorial` — 建筑编辑风格（杂志排版）
2. `technical_diagram` — 技术图纸（精确标注）
3. `hero_statement` — 英雄声明（大图+标题）
4. `data_narrative` — 数据叙事（图表为主）
5. `section_reveal` — 剖面揭示（对角线/层次）

**工具函数：**
- `get_preset_strategy(archetype)` — 获取预设策略
- `suggest_strategy_for_content(...)` — 启发式内容分析建议

### 2. VisualIntent 升级 (`archium/domain/visual/visual_intent.py`)

**向后兼容的升级：**
```python
# 原来：
composition_strategy: str = ""

# 现在：
composition_strategy: CompositionStrategy | str | None = None
```

**新增方法：**
- `get_composition_strategy()` — 获取结构化策略（如果有）
- `has_structured_composition()` — 判断是否结构化

**验证器：**
- `_coerce_composition_strategy` — 自动转换 dict → CompositionStrategy

**兼容性：**
- 接受 `CompositionStrategy` 对象（新）
- 接受 `str`（遗留）
- 接受 `dict`（自动转换）
- 接受 `None`

### 3. 模块导出更新 (`archium/domain/visual/__init__.py`)

导出所有新类型和函数，确保其他模块可以访问。

### 4. 完整测试套件

**测试文件 1：**`tests/unit/visual/test_composition_strategy.py`
- 模型验证测试
- 字段验证测试（drawing_priority 0-1 范围）
- 辅助方法测试（is_hero_dominated, is_editorial_style 等）
- 预设原型测试（5个预设的有效性）
- 序列化/反序列化测试
- 策略建议启发式测试

**测试文件 2：**`tests/unit/visual/test_visual_intent_composition.py`
- VisualIntent 与 CompositionStrategy 集成测试
- 向后兼容性测试（字符串/None）
- 自动转换测试（dict → CompositionStrategy）
- 序列化往返测试

### 5. LLM Prompt 指南 (`docs/visual/composition-strategy-prompt-guide.md`)

完整的 LLM 生成指南，包括：
- 字段定义和可选值
- 4个真实场景示例（JSON 格式）
- 决策树（如何选择原型）
- 与 Layout 生成的集成说明
- 向后兼容性说明

## 关键设计决策

### 1. 不是"增加更多元素属性"
我们**没有**在 LayoutElement 上加更多 CSS 属性。我们创建的是**设计判断层**。

### 2. 不是"新增 Agent"
我们**没有**创建 CompositionAgent。策略仍然由 Visual 角色生成，但现在是结构化输出。

### 3. 向后兼容
现有系统中的字符串 `composition_strategy` 继续工作，不会破坏任何东西。

### 4. 确定性执行
结构化策略可以被 Layout generator **精确执行**，而不是"解析字符串描述"。

## 如何使用

### 生成时（LLM）

```python
# 在生成 VisualIntent 时
intent = VisualIntent(
    slide_id=...,
    communication_goal="展示场地约束",
    composition_strategy=CompositionStrategy(
        archetype="architectural_editorial",
        dominant_axis=CompositionAxis.HORIZONTAL,
        reading_path=ReadingPathType.Z_PATTERN,
        tension=VisualTension.ASYMMETRIC,
        balance=VisualBalance.LEFT_WEIGHTED,
        image_role=ImageRole.DOMINANT,
        typography_role=TypographyRole.EDITORIAL,
        white_space=WhiteSpaceStrategy.GENEROUS,
    )
)
```

### 读取时（Layout Generator）

```python
# 在 LayoutPlanningService 中
strategy = intent.get_composition_strategy()
if strategy:
    # 精确执行设计判断
    if strategy.is_hero_dominated():
        # 使用 hero layout family
        pass
    if strategy.balance == VisualBalance.LEFT_WEIGHTED:
        # 左侧权重更高
        pass
    if strategy.white_space == WhiteSpaceStrategy.GENEROUS:
        # 增加留白
        pass
```

### 使用预设

```python
from archium.domain.visual import get_preset_strategy

strategy = get_preset_strategy("technical_diagram")
intent.composition_strategy = strategy
```

## 下一步建议

### 短期（立即）
1. ✅ 创建模型和测试（已完成）
2. ⏭ 更新 `VisualIntentService.generate_for_slide()` prompt
3. ⏭ 更新 `LayoutPlanningService` 读取策略字段

### 中期
4. 在 `LayoutFamilyRegistry` 中标注每个 family 适配的策略类型
5. Candidate 选择时匹配 `composition_strategy.archetype`
6. 添加 Golden Case：同一内容 + 不同策略 → 验证视觉差异

### 长期
7. Vision Critic 评估策略执行质量
8. 用户在 Studio 中切换策略原型
9. 从真实建筑作品中学习新原型

## 文件清单

### 新增文件
1. `archium/domain/visual/composition_strategy.py` — 核心模型（470 行）
2. `tests/unit/visual/test_composition_strategy.py` — 测试（340 行）
3. `tests/unit/visual/test_visual_intent_composition.py` — 集成测试（120 行）
4. `docs/visual/composition-strategy-prompt-guide.md` — LLM 指南（380 行）

### 修改文件
1. `archium/domain/visual/visual_intent.py` — 升级字段类型
2. `archium/domain/visual/__init__.py` — 导出新类型

### 影响范围
- ✅ 不破坏现有代码（向后兼容）
- ✅ 不改变数据库 schema（JSON 字段）
- ⚠️ 需要更新 prompt（LLM 输出格式）
- ⚠️ 需要更新 LayoutPlanningService（读取策略）

## 验证方式

```bash
# 运行测试
pytest tests/unit/visual/test_composition_strategy.py -v
pytest tests/unit/visual/test_visual_intent_composition.py -v

# 类型检查
mypy archium/domain/visual/composition_strategy.py
mypy archium/domain/visual/visual_intent.py

# 导入验证
python -c "from archium.domain.visual import CompositionStrategy, get_preset_strategy; print('OK')"
```

## 设计原则回顾

你的原始分析中提到的关键点，我们都遵循了：

### ✅ 我们做到了
- 创建了**建筑师做版式时的思维模型**
- 是**设计判断**，不是**元素堆砌**
- **结构化策略**，不是字符串描述
- 可以被**精确执行**，不是启发式解析
- **不增加 Agent**，能力挂在 Visual 席位
- **向后兼容**，不破坏现有系统

### ✅ 我们避免了
- ❌ 不是 Canva + AI
- ❌ 不是 PPT 模板市场风格
- ❌ 不是增加更多 CSS 属性
- ❌ 不是"医院模板/校园模板"固定套版

## 总结

这个实现**填补了从 VisualIntent 到 LayoutPlan 之间的设计判断断层**。

现在链路是：
```
ArtDirection (整体语言)
  ↓
DeckCompositionPlan (节奏/密度)
  ↓
VisualIntent + CompositionStrategy (单页构图策略) ← 新增！
  ↓
LayoutPlan (几何坐标)
```

这正是你分析中指出的缺失部分。
