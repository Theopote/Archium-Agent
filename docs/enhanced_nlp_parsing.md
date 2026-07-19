# 增强的自然语言解析功能

## 概述

本系统为 Archium Agent 的视觉编辑服务提供了增强的自然语言解析能力，支持更复杂的编辑指令。

## 架构

### 混合解析策略

系统采用三层解析架构：

1. **增强规则解析器** (`EnhancedNLPParser`) - 快速、确定性的解析
2. **LLM 解析器** (`LLMIntentParser`) - 处理复杂指令
3. **混合路由** (`HybridIntentParser`) - 智能选择解析策略

```
用户输入
    ↓
混合路由器
    ├─→ 简单指令 → 规则解析器 → 返回结果
    └─→ 复杂指令 → LLM 解析器 → 返回结果
                    ↓ (失败)
                规则解析器 (回退)
```

## 支持的复杂指令类型

### 1. 相对调整（Relative Adjustment）

支持程度副词，精确控制修改强度。

**示例：**
```python
"稍微放大主图"        # 强度: 0.3
"再大一点"           # 强度: 0.4
"更大"              # 强度: 0.5
"非常大"            # 强度: 0.8
```

**映射表：**
- `稍微`, `一点点`, `略微` → 0.2-0.3 (轻微调整)
- `再`, `一点` → 0.3-0.4 (适度调整)
- `更` → 0.5 (明显调整)
- `很` → 0.7 (较大调整)
- `非常`, `极` → 0.8-0.9 (显著调整)

### 2. 条件约束（Constraint）

在执行操作时保持某些元素不变。

**示例：**
```python
"放大主图但不要盖住标题"          # 负向约束
"保持图片不动，只调整文字"        # 保留约束
"不要改标题"                     # 禁止触碰
"只把说明挪到右侧"               # 限定范围
```

**约束类型：**
- `negative_constraint` - "但不要..."
- `preserve` - "保持...不动"
- `dont_touch` - "不要改..."
- `only` - "只..."

### 3. 多步骤操作（Multi-step）

涉及多个元素的协调变化。

**示例：**
```python
"第二张照片换到第一张位置"        # 位置交换
"把说明移到右侧"                # 移动元素
"图片和文字互换"                # 元素互换
"重新排列所有卡片"              # 批量重排
```

**操作类型：**
- `swap` - 交换位置
- `move_to` - 移动到指定位置
- `exchange` - 互换
- `rearrange` - 重新排列

### 4. 语义理解（Semantic）

理解抽象的设计意图并转换为具体操作。

**示例：**
```python
"突出结论"     # → 增大尺寸 + 增加对比度 + 重新定位
"收紧版面"     # → 减少间距 + 增加密度
"更专业"       # → 简化 + 对齐 + 一致间距
"让它更清晰"   # → 增加留白 + 放大文字 + 减少元素
```

**语义映射：**
| 语义词 | 设计意图 | 具体操作 |
|--------|---------|---------|
| 突出 | emphasis | increase_size, add_contrast, reposition |
| 强调 | emphasis | increase_size, add_contrast |
| 收紧 | tighten | reduce_spacing, increase_density |
| 放松 | relax | increase_spacing, reduce_density |
| 专业 | professional | simplify, align, consistent_spacing |
| 清晰 | clarity | increase_whitespace, larger_text |
| 紧凑 | compact | reduce_spacing, smaller_elements |
| 平衡 | balance | redistribute_elements, center_align |

## 使用示例

### 基本用法

```python
from archium.application.visual.visual_edit_service import VisualEditService
from sqlalchemy.orm import Session

# 初始化服务（启用 LLM）
service = VisualEditService(session, use_llm=True)

# 简单指令（规则解析）
result = service.apply_text(slide_id, "放大主图")

# 复杂指令（混合解析）
result = service.apply_text(slide_id, "主图稍微再大一点，不要盖住标题")
```

### 高级用法

```python
from archium.domain.visual.hybrid_parser import create_hybrid_parser
from archium.infrastructure.llm.factory import create_llm_provider

# 创建混合解析器
llm_provider = create_llm_provider(settings)
parser = create_hybrid_parser(llm_provider, use_llm=True)

# 解析复杂指令
parsed = parser.parse("保持图纸不动，只把说明挪到右侧，但不要改标题")

if parsed:
    print(f"意图: {parsed.intent}")
    print(f"参数: {parsed.params}")
    print(f"修饰符: {parsed.modifiers}")
    print(f"置信度: {parsed.confidence}")
```

## 复杂指令示例

### 示例 1: 程度 + 约束
```
输入: "主图稍微再大一点，不要盖住标题"

解析结果:
  intent: ENLARGE_HERO
  params:
    adjustment_strength: 0.4
    constraints:
      - type: negative_constraint
        target: "标题"
  confidence: 0.75
```

### 示例 2: 保留 + 限定操作
```
输入: "保持图纸不动，只把说明挪到右侧"

解析结果:
  intent: (需要 LLM 处理多步骤)
  params:
    constraints:
      - type: preserve
        target: "图纸"
    multi_step_operations:
      - operation: move_to
        targets: ["说明", "右侧"]
  confidence: 0.65
```

### 示例 3: 语义 + 约束
```
输入: "这页太散，收紧一点但字号不要变"

解析结果:
  intent: INCREASE_WHITESPACE (反向) 或语义操作
  params:
    semantic_operations: ["reduce_spacing", "increase_density"]
    constraints:
      - type: preserve
        target: "字号"
  confidence: 0.60
```

### 示例 4: 多步骤位置操作
```
输入: "第二张照片换到第一张位置"

解析结果:
  intent: (需要 LLM 处理)
  params:
    multi_step_operations:
      - operation: swap
        targets: ["第二张照片", "第一张位置"]
  confidence: 0.70
```

### 示例 5: 保留布局 + 语义强调
```
输入: "保留这个排版，只把结论更突出"

解析结果:
  intent: (需要 LLM 处理)
  params:
    constraints:
      - type: preserve
        target: "排版"
    semantic_operations: ["increase_size", "add_contrast"]
  confidence: 0.68
```

## 置信度评分

解析器会为每个结果分配置信度分数 (0.0-1.0)：

- **0.8-1.0**: 高置信度，规则精确匹配
- **0.6-0.8**: 中等置信度，有修饰符但可处理
- **0.5-0.6**: 低置信度，复杂指令，依赖 LLM
- **< 0.5**: 无法理解，返回 None

## 性能优化

### 规则优先策略
- 简单指令直接使用规则解析（~1ms）
- 只在必要时调用 LLM（~200-500ms）
- 启发式预判断避免不必要的 LLM 调用

### LLM 调用条件
自动判断以下情况需要 LLM：
- 包含多个约束条件
- 指令长度 > 40 字符
- 多个逗号/句号分隔的子句
- 包含"和"、"并且"等连接词
- 包含序列或比较词汇

## 配置

### 启用 LLM 解析

```python
# 在 settings 中配置 LLM
settings.llm_provider = "openai"  # 或 "anthropic"
settings.llm_api_key = "your-api-key"

# 创建服务时启用
service = VisualEditService(session, use_llm=True)
```

### 调整置信度阈值

```python
from archium.domain.visual.hybrid_parser import HybridIntentParser

# 自定义阈值
HybridIntentParser.CONFIDENCE_THRESHOLD = 0.65  # 默认 0.7
```

## 扩展

### 添加新的语义词

编辑 `archium/domain/visual/nlp_parser.py`:

```python
SEMANTIC_VERBS = {
    "突出": ("emphasis", ["increase_size", "add_contrast"]),
    "你的新词": ("your_semantic", ["operation1", "operation2"]),
}
```

### 添加新的约束模式

```python
CONSTRAINT_PATTERNS = [
    (r"你的正则模式", "constraint_type"),
]
```

## 限制

当前版本的已知限制：

1. **复杂嵌套指令**: 超过3个子句的嵌套指令可能需要分解
2. **歧义消解**: 某些模糊指令可能需要用户澄清
3. **上下文依赖**: 不会记忆先前的编辑历史
4. **多语言**: 当前主要支持中文和英文

## 测试

运行测试验证功能：

```bash
# 运行增强解析器测试
python test_nlp_standalone.py

# 运行完整单元测试
pytest tests/unit/visual/test_enhanced_nlp_parser.py -v
```

## 故障排除

### LLM 解析失败
- 检查 API 密钥配置
- 验证网络连接
- 系统会自动回退到规则解析

### 置信度过低
- 尝试使用更明确的语言
- 分解复杂指令为多个简单指令
- 使用预设按钮代替自然语言

### 误解析
- 检查输入是否包含拼写错误
- 使用标准术语（如"主图"而非"大图"）
- 查看日志了解解析过程

## 未来改进

计划中的增强功能：

- [ ] 支持更多语言（日语、韩语等）
- [ ] 上下文感知解析（记忆历史操作）
- [ ] 更精细的语义理解（设计风格识别）
- [ ] 交互式歧义消解（询问用户意图）
- [ ] 批量操作支持（"所有标题"、"全部图片"）
- [ ] 相对引用（"上一个"、"这个旁边的"）
