# 快速入门 - 增强自然语言解析

## 5 分钟快速上手

### 1. 查看演示

```bash
cd /path/to/Archium-Agent
python demo_nlp_parsing_fixed.py
```

这将展示新解析器如何处理各种复杂指令。

### 2. 运行测试

```bash
# 独立测试（无需依赖）
python test_nlp_standalone.py

# 完整单元测试（需要项目依赖）
pytest tests/unit/visual/test_enhanced_nlp_parser.py -v
```

### 3. 在代码中使用

#### 基础用法（推荐）

```python
from archium.application.visual.visual_edit_service import VisualEditService

# 初始化服务
service = VisualEditService(session, use_llm=True)

# 使用复杂指令
result = service.apply_text(
    slide_id=your_slide_id,
    text="稍微放大主图但不要盖住标题"
)

print(f"成功: {result.message}")
```

#### 高级用法（直接使用解析器）

```python
from archium.domain.visual.hybrid_parser import create_hybrid_parser
from archium.infrastructure.llm.factory import create_llm_provider

# 创建解析器
llm = create_llm_provider(settings)
parser = create_hybrid_parser(llm, use_llm=True)

# 解析指令
parsed = parser.parse("保持图纸不动，只把说明挪到右侧")

if parsed:
    print(f"意图: {parsed.intent}")
    print(f"置信度: {parsed.confidence}")
    print(f"参数: {parsed.params}")
    print(f"修饰符: {len(parsed.modifiers)} 个")
```

## 支持的指令类型

### ✅ 简单指令（规则解析，1ms）
```python
"放大主图"
"减少文字"
"增加留白"
"切换版式"
```

### ✅ 带程度副词（规则解析，1ms）
```python
"稍微放大主图"          # 强度 0.3
"再大一点"              # 强度 0.4
"更大的主图"            # 强度 0.5
"非常大"                # 强度 0.8
```

### ✅ 带约束条件（规则解析，1ms）
```python
"放大主图但不要盖住标题"
"减少文字保持图片不动"
"只调整标题"
```

### 🔄 复杂指令（LLM 解析，200-500ms）
```python
"主图稍微再大一点，不要盖住标题"
"保持图纸不动，只把说明挪到右侧"
"这页太散，收紧一点但字号不要变"
```

## 配置 LLM（可选）

如果不配置 LLM，系统会自动使用规则解析器（速度快但能力有限）。

### OpenAI 配置

```python
# settings.py 或环境变量
settings.llm_provider = "openai"
settings.llm_api_key = "sk-..."
settings.llm_model = "gpt-4"  # 或 "gpt-3.5-turbo"
```

### Anthropic 配置

```python
settings.llm_provider = "anthropic"
settings.llm_api_key = "sk-ant-..."
settings.llm_model = "claude-3-sonnet-20240229"
```

## 常见问题

### Q: 是否必须使用 LLM？
**A:** 不是。不启用 LLM 时，系统使用增强规则解析器，可以处理大部分常见指令。

### Q: LLM 解析有多慢？
**A:** 通常 200-500ms。简单指令会被规则解析器拦截（~1ms），只有复杂指令才会调用 LLM。

### Q: 费用如何？
**A:** 
- 规则解析：完全免费
- LLM 解析：每次约 $0.001-0.01（取决于模型）
- 系统会优先使用规则解析以降低成本

### Q: 如何调试解析结果？
**A:** 使用解析器的 `parse()` 方法查看详细结果：

```python
parsed = parser.parse("你的指令")
print(f"置信度: {parsed.confidence}")
print(f"修饰符: {[m.description for m in parsed.modifiers]}")
print(f"参数: {parsed.params}")
```

### Q: 为什么某些指令无法识别？
**A:** 可能的原因：
1. 指令过于模糊或歧义
2. 使用了非标准术语
3. LLM 未启用且指令太复杂

**解决方法：**
1. 使用更明确的语言
2. 启用 LLM 支持
3. 查看文档中的标准术语

## 下一步

- 📖 阅读完整文档：`docs/enhanced_nlp_parsing.md`
- 📊 查看实施总结：`IMPLEMENTATION_SUMMARY.md`
- 🧪 编写自定义测试用例
- 🎯 根据项目需求扩展语义词和约束模式

## 获取帮助

- 查看测试用例：`tests/unit/visual/test_enhanced_nlp_parser.py`
- 运行演示脚本：`demo_nlp_parsing_fixed.py`
- 阅读源码注释：所有函数都有详细的 docstring
