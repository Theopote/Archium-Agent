# 复杂自然语言解析实现分析


> **文档状态：历史快照。**
> 本文记录特定阶段的分析、实施、验收或计划，可能包含已过时的路径、状态和结论。
> 当前行为以代码、测试、`README.md`、`docs/README.md` 及现行专题文档为准。
## 执行时间
2026-07-19

---

## 当前实现状态

### ✅ 已实现的解析层

#### 1. Rule Parser（规则解析器）
**文件**：`archium/domain/visual/edit_intent.py`

**功能**：
- 基础关键词匹配
- 固定模式识别
- 简单意图解析

**限制**：
- 只能理解固定关键词
- 不支持相对调整
- 不支持约束条件

#### 2. Enhanced NLP Parser（增强NLP解析器）
**文件**：`archium/domain/visual/nlp_parser.py`

**新增功能**：
```python
class ModifierType(StrEnum):
    RELATIVE = "relative"      # 稍微、再大一点
    CONSTRAINT = "constraint"  # 但不要、保持...不动
    MULTI_STEP = "multi_step"  # 换位置、重新排列
    SEMANTIC = "semantic"      # 突出、收紧、更专业
```

**支持的复杂性**：
- ✅ 程度副词（稍微、非常、略微）
- ✅ 约束模式（但不要、保持...不动）
- ✅ 语义动词（突出、收紧、专业）
- ✅ 位置操作（换到、移到、互换）

**示例解析**：
```python
输入："稍微放大主图"
输出：ParsedIntent(
    intent=ENLARGE_HERO,
    params={},
    modifiers=[Modifier(type=RELATIVE, value=0.3)],
    confidence=0.85
)

输入："保持图纸不动，把说明放右边"
输出：ParsedIntent(
    intent=MOVE_TO,
    params={"target": "说明", "position": "右边"},
    modifiers=[
        Modifier(type=CONSTRAINT, target="图纸", value="preserve")
    ],
    confidence=0.75
)
```

#### 3. LLM Parser（LLM解析器）
**文件**：`archium/domain/visual/llm_parser.py`

**功能**：
- 处理复杂自然语言
- 理解隐含意图
- 多步骤操作解析

**输出**：
```json
{
  "intent": "change_layout",
  "constraints": ["keep drawing locked"],
  "relative_adjustments": {"degree": "slightly"},
  "multi_step_operations": [
    {"operation": "move", "targets": ["说明"], "position": "右边"}
  ]
}
```

#### 4. Hybrid Parser（混合解析器）
**文件**：`archium/domain/visual/hybrid_parser.py`

**策略**：
```
1. 先尝试 Enhanced NLP Parser（快速、确定性）
2. 如果置信度 < 0.7，回退到 LLM Parser
3. 选择置信度更高的结果
```

**置信度阈值**：
```python
CONFIDENCE_THRESHOLD = 0.7  # 低于此值时尝试 LLM
```

---

## ✅ 解析层评估

### 进步

**解决的问题**：
1. ✅ 不再局限于固定关键词
2. ✅ 支持相对调整（稍微、非常）
3. ✅ 支持约束条件（但不要、保持...不动）
4. ✅ 支持语义理解（突出、收紧、专业）
5. ✅ 支持多步骤操作解析

**质量提升**：
- 从"只能理解预设命令"
- 到"理解自然语言表达"

**示例对比**：

| 指令 | 旧解析器 | 新解析器 |
|------|---------|---------|
| "放大主图" | ✅ 识别 | ✅ 识别 |
| "稍微放大主图" | ❌ 不识别 | ✅ 识别 + 程度=0.3 |
| "保持图纸不动，放大主图" | ❌ 不识别 | ✅ 识别 + 约束 |
| "让标题更突出" | ❌ 不识别 | ✅ 识别为语义操作 |

---

## ❌ 缺失的执行层机制

### 问题：解析 ≠ 执行

**当前状态**：
```
用户输入："保持图纸不动，把说明放右边并减少两行文字"
  ↓
Hybrid Parser 解析成功 ✅
  ↓
输出结构化意图：
  - intent: MOVE_TO
  - modifiers: [CONSTRAINT(preserve drawing), MULTI_STEP]
  - params: {target: "说明", position: "右边"}
  ↓
❌ 执行层缺失：没有事务机制
```

### 缺失的组件

#### 1. ❌ 复合命令执行器

**需要**：`CompositeCommandExecutor`

**功能**：
```python
class CompositeCommandExecutor:
    def execute_multi_step(
        self,
        parsed_intent: ParsedIntent,
        slide_id: UUID,
    ) -> ExecutionResult:
        """
        执行多步骤操作，带事务支持
        
        步骤：
        1. 解析为原子操作序列
        2. 验证约束（锁定检查）
        3. 按顺序执行每个操作
        4. 每步保存 Revision
        5. 失败时全部回滚
        """
```

**当前问题**：
- `VisualEditService.apply_text()` 只执行单一意图
- `SlideEditExecutionService.execute()` 只路由到单一服务
- 没有复合命令的协调器

#### 2. ❌ 事务机制

**需要**：
```python
class VisualEditTransaction:
    def __init__(self, slide_id: UUID):
        self.slide_id = slide_id
        self.operations: list[Operation] = []
        self.checkpoints: list[Checkpoint] = []
    
    def add_operation(self, op: Operation):
        """添加操作到事务"""
        self.operations.append(op)
    
    def execute(self) -> TransactionResult:
        """执行所有操作，失败时回滚"""
        for i, op in enumerate(self.operations):
            # 保存检查点
            checkpoint = self._save_checkpoint()
            self.checkpoints.append(checkpoint)
            
            try:
                op.execute()
            except Exception as e:
                # 回滚到事务开始
                self._rollback_to_start()
                return TransactionResult(success=False, error=e)
        
        return TransactionResult(success=True)
    
    def _rollback_to_start(self):
        """回滚所有已执行的操作"""
        for checkpoint in reversed(self.checkpoints):
            checkpoint.restore()
```

**当前问题**：
- 没有事务边界
- 操作失败时不会自动回滚
- 可能出现部分写入状态

#### 3. ❌ 约束验证器

**需要**：
```python
class ConstraintValidator:
    def validate_before_execution(
        self,
        operations: list[Operation],
        constraints: list[Modifier],
        current_plan: LayoutPlan,
    ) -> ValidationResult:
        """
        执行前验证约束
        
        检查：
        1. 锁定元素不能被修改
        2. 保持约束（preserve）被遵守
        3. 排他约束（only）被遵守
        """
```

**当前问题**：
- `assert_element_editable()` 只检查单个元素
- 没有全局约束验证
- 解析出的约束没有被强制执行

#### 4. ❌ 操作分解器

**需要**：
```python
class OperationDecomposer:
    def decompose(
        self,
        parsed_intent: ParsedIntent,
    ) -> list[AtomicOperation]:
        """
        将复合意图分解为原子操作序列
        
        示例：
        输入："保持图纸不动，把说明放右边并减少两行文字"
        
        输出：
        [
            LockOperation(element_id="drawing"),
            MoveOperation(element_id="caption", position="right"),
            ReduceTextOperation(element_id="caption", lines=2),
        ]
        """
```

**当前问题**：
- 解析器输出 `ParsedIntent`，但没有分解为可执行操作
- `multi_step_operations` 在 params 中，但没有执行器处理

#### 5. ❌ Revision 链管理

**需要**：
```python
class RevisionChainManager:
    def create_revision_chain(
        self,
        slide_id: UUID,
        operations: list[Operation],
    ) -> RevisionChain:
        """
        为多步骤操作创建 Revision 链
        
        每个操作保存一个 Revision，
        形成可追溯、可回滚的历史链
        """
    
    def rollback_chain(
        self,
        chain_id: UUID,
    ) -> RollbackResult:
        """
        回滚整个操作链
        
        撤销所有相关的 Revision，
        恢复到操作前的状态
        """
```

**当前问题**：
- `VisualHistoryService` 只处理单个 Revision
- 没有 Revision 链的概念
- 不能整体撤销复合操作

---

## 验收标准缺口

### 用户输入示例

```
"保持图纸不动，把说明放右边并减少两行文字"
```

### 应该分解为

```python
[
    LockOperation(
        element_id="drawing",
        locked=True,
    ),
    MoveOperation(
        element_id="caption",
        position="right",
        preserve_size=True,
    ),
    ReduceTextOperation(
        element_id="caption",
        reduce_lines=2,
    ),
]
```

### 验收检查清单

| 要求 | 状态 | 说明 |
|------|------|------|
| **解析** | | |
| 能否解析复合指令 | ✅ | Hybrid Parser 可以解析 |
| 能否识别约束 | ✅ | 识别"保持...不动" |
| 能否识别多步骤 | ✅ | 识别"并" |
| **分解** | | |
| 能否分解为原子操作 | ❌ | **缺失 OperationDecomposer** |
| 顺序是否正确 | ❌ | **未验证** |
| **执行** | | |
| 能否按顺序执行 | ⚠️ | 只能执行单一操作 |
| 锁定是否生效 | ⚠️ | 单操作锁定有效，复合未验证 |
| 每步是否保存 Revision | ⚠️ | 单操作保存，复合未验证 |
| **失败处理** | | |
| 失败时是否回滚 | ❌ | **缺失事务机制** |
| 是否避免部分写入 | ❌ | **缺失事务机制** |
| **撤销** | | |
| 能否整体撤销 | ❌ | **缺失 Revision 链管理** |

### 当前判定

**解析层**：✅ **通过**
- 规则解析 + NLP增强 + LLM回退 = 完整
- 支持相对调整、约束、多步骤、语义理解

**执行层**：❌ **未通过**
- 缺少复合命令执行器
- 缺少事务机制
- 缺少约束验证
- 缺少操作分解器
- 缺少 Revision 链管理

**整体评估**：⚠️ **部分完成**
- 单意图增强：✅ 通过
- 复合操作端到端：❌ **条件不满足**

---

## 实际可能的执行路径（当前）

### 用户输入
```
"保持图纸不动，把说明放右边并减少两行文字"
```

### 实际发生的事情

```python
# 1. 解析成功
parsed = hybrid_parser.parse(text)
# 输出：ParsedIntent(
#   intent=MOVE_TO,
#   params={"target": "说明", "position": "右边"},
#   modifiers=[
#     Modifier(type=CONSTRAINT, target="图纸", value="preserve"),
#     Modifier(type=MULTI_STEP, value={...}),
#   ],
#   confidence=0.75
# )

# 2. 传递给执行服务
result = visual_edit_service.apply_text(slide_id, text)

# 3. 执行服务的实际行为
def apply_text(self, slide_id, text):
    parsed = self._hybrid_parser.parse(text)
    
    # ❌ 问题：只使用主 intent，忽略 modifiers
    intent = parsed.intent  # MOVE_TO
    params = parsed.params  # {"target": "说明", "position": "右边"}
    
    # ❌ 问题：modifiers 中的约束和多步骤被丢弃
    # modifiers 包含：
    # - CONSTRAINT: 保持图纸不动
    # - MULTI_STEP: 减少两行文字
    # 但这些都没有被执行！
    
    # 只执行主 intent
    return self._apply_single_intent(slide_id, intent, params)
```

### 结果

**实际执行**：
- ✅ 把说明移到右边

**未执行**：
- ❌ 保持图纸不动（约束被忽略）
- ❌ 减少两行文字（多步骤被忽略）

**用户体验**：
- 用户看到"说明"移动了
- 但"图纸"也可能移动了（如果布局引擎重新排列）
- "文字"没有减少

---

## 实现路径建议

### Phase 1：操作分解器（1周）

**创建**：`archium/application/visual/operation_decomposer.py`

```python
class OperationDecomposer:
    def decompose(
        self,
        parsed_intent: ParsedIntent,
        slide_id: UUID,
    ) -> list[AtomicOperation]:
        """分解复合意图为原子操作"""
        operations = []
        
        # 1. 处理约束（转换为锁定操作）
        for modifier in parsed_intent.modifiers:
            if modifier.type == ModifierType.CONSTRAINT:
                if modifier.value == "preserve":
                    operations.append(
                        LockOperation(
                            element_id=self._resolve_element(modifier.target),
                            locked=True,
                        )
                    )
        
        # 2. 处理主操作
        operations.append(
            self._intent_to_operation(
                parsed_intent.intent,
                parsed_intent.params,
            )
        )
        
        # 3. 处理多步骤
        if "multi_step_operations" in parsed_intent.params:
            for step in parsed_intent.params["multi_step_operations"]:
                operations.append(
                    self._step_to_operation(step)
                )
        
        return operations
```

### Phase 2：事务执行器（1周）

**创建**：`archium/application/visual/transaction_executor.py`

```python
class TransactionExecutor:
    def execute_transaction(
        self,
        operations: list[AtomicOperation],
        slide_id: UUID,
    ) -> TransactionResult:
        """执行事务，失败时回滚"""
        checkpoints = []
        executed = []
        
        try:
            for op in operations:
                # 保存检查点
                checkpoint = self._create_checkpoint(slide_id)
                checkpoints.append(checkpoint)
                
                # 执行操作
                op.execute(self._session)
                executed.append(op)
                
                # 保存 Revision
                self._save_revision(slide_id, op)
            
            # 提交事务
            self._session.commit()
            return TransactionResult(success=True, executed=executed)
        
        except Exception as e:
            # 回滚所有操作
            self._session.rollback()
            self._restore_from_checkpoints(checkpoints)
            return TransactionResult(success=False, error=e)
```

### Phase 3：集成到执行服务（3天）

**修改**：`archium/application/visual/visual_edit_service.py`

```python
def apply_text(self, slide_id, text):
    # 1. 解析
    parsed = self._hybrid_parser.parse(text)
    
    # 2. 分解为操作
    operations = self._decomposer.decompose(parsed, slide_id)
    
    # 3. 验证约束
    validation = self._constraint_validator.validate(
        operations,
        self._get_current_plan(slide_id)
    )
    if not validation.valid:
        raise WorkflowError(validation.error)
    
    # 4. 执行事务
    result = self._transaction_executor.execute_transaction(
        operations,
        slide_id,
    )
    
    return result
```

### Phase 4：Revision 链管理（3天）

**创建**：`archium/application/visual/revision_chain_manager.py`

```python
class RevisionChainManager:
    def create_chain(
        self,
        slide_id: UUID,
        operations: list[Operation],
    ) -> RevisionChain:
        """创建 Revision 链"""
        chain_id = uuid4()
        revisions = []
        
        for op in operations:
            revision = self._history.save_revision(
                slide_id=slide_id,
                operation=op,
                chain_id=chain_id,
            )
            revisions.append(revision)
        
        return RevisionChain(id=chain_id, revisions=revisions)
    
    def rollback_chain(self, chain_id: UUID):
        """回滚整个链"""
        revisions = self._history.get_chain(chain_id)
        for revision in reversed(revisions):
            revision.rollback()
```

---

## 风险和注意事项

### 技术风险

1. **性能影响**
   - 多个检查点会增加开销
   - 缓解：只在复合操作时启用事务

2. **复杂度增加**
   - 事务机制增加代码复杂度
   - 缓解：清晰的接口设计，充分测试

3. **回滚可靠性**
   - 回滚可能失败
   - 缓解：使用数据库事务 + 应用层检查点

### 用户体验风险

1. **执行时间增加**
   - 复合操作需要更多时间
   - 缓解：显示进度条，明确告知用户

2. **失败信息不清晰**
   - 哪一步失败了？
   - 缓解：详细的错误信息，指出失败的操作

---

## 总结

### ✅ 已完成

**解析层**：
- Enhanced NLP Parser
- LLM Parser
- Hybrid Parser
- 支持相对调整、约束、多步骤、语义理解

### ❌ 缺失

**执行层**：
- 操作分解器
- 事务执行器
- 约束验证器
- Revision 链管理器

### 🎯 判定

**单意图增强**：✅ **通过**
- "稍微放大主图" 可以正确解析和执行

**复合操作端到端**：❌ **未通过**
- "保持图纸不动，把说明放右边并减少两行文字"
- 可以解析 ✅
- 不能完整执行 ❌（只执行主操作，约束和多步骤被忽略）
- 没有事务保证 ❌
- 不能整体撤销 ❌

### 📋 推荐行动

**立即**：
1. 承认执行层缺失
2. 标注当前状态为"解析完成，执行待实现"

**本月**：
3. 实现操作分解器
4. 实现事务执行器

**下月**：
5. 集成到主工作流
6. 完整端到端测试

---

生成时间：2026-07-19  
作者：Kiro (Claude Sonnet 5)  
状态：分析完成
