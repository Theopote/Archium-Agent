# Content Adaptation 安全性分析报告


> **文档状态：历史快照。**
> 本文记录特定阶段的分析、实施、验收或计划，可能包含已过时的路径、状态和结论。
> 当前行为以代码、测试、`README.md`、`docs/README.md` 及现行专题文档为准。
## 问题诊断

### 文件：`content_adaptation_service.py`

---

## 问题 1：硬截断导致语义破坏

### 位置：第 186-190 行

```python
def _apply_convert_to_bullets(self, slide: SlideSpec):
    if updated.key_points:
        summary, applied, reason = smart_shorten_text(updated.message, 72)
        if not applied:
            summary = shorten_repetitive_expression(updated.message)
            if len(summary) > 80:
                summary = summary[:79].rstrip() + "…"  # ❌ 危险的硬截断
```

### 危害分析

#### A. 截断数值单位
```python
原文: "项目预算为 1,250,000 美元，较去年增长 15%"
硬截断: "项目预算为 1,250,000 美元，较去年增长 1…"  # ❌ 丢失单位
正确: "项目预算 125 万美元，增长 15%"  # ✅ 保留语义
```

#### B. 截断专有名词
```python
原文: "Apple Park 总部位于 Cupertino，占地 175 英亩"
硬截断: "Apple Park 总部位于 Cuper…"  # ❌ 地名不完整
正确: "Apple Park 总部在 Cupertino"  # ✅ 完整名词
```

#### C. 截断否定关系
```python
原文: "该方案不适用于中小企业，仅针对大型客户设计"
硬截断: "该方案不适用于中小企业，仅针对大…"  # ❌ 丢失"仅针对"的限定
正确: "该方案仅针对大型客户"  # ✅ 保留关键限定
```

#### D. 截断引用语义
```python
原文: "根据《2023年市场报告》显示，增长率达到 8.5%"
硬截断: "根据《2023年市场报告》显示，增长…"  # ❌ 丢失具体数据
正确: "《2023市场报告》：增长率 8.5%"  # ✅ 保留关键数据
```

### 问题根源

**代码逻辑**：
```python
if not applied:  # smart_shorten_text 失败
    summary = shorten_repetitive_expression(updated.message)  # 尝试去重
    if len(summary) > 80:
        summary = summary[:79] + "…"  # 作为最后的fallback，直接截断
```

**为什么这是错误的**：
1. ❌ **没有语言感知** - 截断点可能在单词/词组中间
2. ❌ **没有语义保护** - 可能破坏数值、名词、否定词
3. ❌ **没有用户确认** - 静默破坏内容
4. ❌ **违反了 smart_shorten_text 的初衷** - 绕过了安全检查

---

## 问题 2：最长要点不等于最重要

### 位置：第 212 行

```python
def _apply_promote_key_message(self, slide: SlideSpec):
    promoted = updated.message.strip()
    if updated.key_points:
        promoted = max(updated.key_points, key=len).strip()  # ❌ 仅基于长度
```

### 危害分析

#### 示例 1：技术总结

```python
key_points = [
    "系统采用微服务架构，包含用户管理、订单处理、支付网关等多个模块",  # 最长
    "核心优势：高可用性",  # 最重要但短
    "部署在 AWS ECS 容器环境中",
]

当前逻辑: 提升 "系统采用微服务架构..." # ❌ 技术细节，不是核心
应该提升: "核心优势：高可用性"  # ✅ 核心价值
```

#### 示例 2：商业提案

```python
key_points = [
    "该方案预计实施周期为 6-8 个月，分为需求调研、系统设计、开发测试三个阶段",  # 最长
    "ROI: 12 个月内回本",  # 最重要但短
    "需要预算 50 万",
]

当前逻辑: 提升 "该方案预计实施周期..." # ❌ 过程细节
应该提升: "ROI: 12 个月内回本"  # ✅ 决策关键
```

#### 示例 3：安全警告

```python
key_points = [
    "系统检测到异常登录行为，来源 IP 地址为 192.168.1.100，位于北京地区",  # 最长
    "立即更改密码",  # 最重要但短
    "建议启用双因素认证",
]

当前逻辑: 提升 "系统检测到异常..." # ❌ 描述性信息
应该提升: "立即更改密码"  # ✅ 行动指令
```

### 问题根源

**错误假设**: 
- 最长的要点 = 最重要的要点
- 信息量 ∝ 字符数

**实际情况**:
- 重要性 ≠ 长度
- 最长的往往是：解释、细节、背景
- 最短的可能是：结论、指令、核心数据

**为什么这只是启发式 fallback**:
```python
# 这个逻辑缺少：
# 1. 语义分析（哪个是结论）
# 2. 重要性评分（关键词、位置）
# 3. 用户确认（让用户选择）
# 4. LLM 判断（理解内容）
```

---

## 影响范围

### 场景 1：用户点击 "转为要点"

```python
原始内容:
  message = "我们的云存储服务提供 99.99% 可用性保证，支持自动备份"
  key_points = []

执行 CONVERT_TO_BULLETS:
  1. smart_shorten_text(message, 72) 返回 applied=False （可能因为无法安全压缩）
  2. shorten_repetitive_expression 也无法缩短
  3. len(summary) = 85 > 80
  4. ❌ 硬截断: "我们的云存储服务提供 99.99% 可用性保证，支持自动备…"
     # 丢失了 "备份" 这个关键功能

应该的行为:
  - 抛出错误，告知用户无法安全压缩
  - 或者提供预览，让用户确认
```

### 场景 2：用户点击 "突出核心信息"

```python
key_points = [
    "实施时间：预计 3 个月，包括需求分析、开发、测试、上线四个阶段",
    "成本降低 40%",  # ← 真正重要
    "使用 Python + Django 技术栈",
]

当前结果:
  提升: "实施时间：预计 3 个月..." # ❌ 项目管理细节

应该结果:
  提升: "成本降低 40%" # ✅ 商业价值
```

---

## 风险评级

| 问题 | 严重性 | 频率 | 风险等级 |
|------|--------|------|---------|
| 硬截断破坏语义 | **高** | 中 | **CRITICAL** |
| 选择最长要点 | **中** | 高 | **HIGH** |

### 硬截断风险

**严重性**: HIGH/CRITICAL
- 可能导致数据错误（数值、单位）
- 可能反转语义（否定词）
- 可能产生误导性结论
- **用户不知情**（静默失败）

**发生频率**: MEDIUM
- 当 `smart_shorten_text` 无法安全缩短时
- 通常在内容密集、专业术语多时

### 最长要点风险

**严重性**: MEDIUM
- 不会破坏数据完整性
- 但会降低信息质量
- 可能突出次要信息

**发生频率**: HIGH
- 每次用户点击 "突出核心信息" 且有多个要点时

---

## 正确的处理方式

### 原则

1. **Never silent fail** - 不能静默破坏内容
2. **Preserve semantics** - 语义完整性 > 长度限制
3. **User confirmation** - 无法安全处理时，让用户决策
4. **Degrade gracefully** - 降级方案也要安全

### 问题 1 的正确方案

#### 方案 A：严格模式（推荐）

```python
def _apply_convert_to_bullets(self, slide: SlideSpec):
    if updated.key_points:
        summary, applied, reason = smart_shorten_text(updated.message, 72)
        if not applied:
            summary = shorten_repetitive_expression(updated.message)
            if len(summary) > 80:
                # ✅ 抛出错误，不做硬截断
                raise WorkflowError(
                    f"无法安全压缩摘要（当前 {len(summary)} 字符）。"
                    f"建议手动编辑或拆分页面。\n原因：{reason}"
                )
```

#### 方案 B：LLM 辅助（最佳）

```python
def _apply_convert_to_bullets(self, slide: SlideSpec):
    if updated.key_points:
        summary, applied, reason = smart_shorten_text(updated.message, 72)
        if not applied:
            # 尝试 LLM 压缩
            if self._llm:
                summary = self._llm_compress(updated.message, max_length=72)
            else:
                # 仍然抛出错误，不做硬截断
                raise WorkflowError(...)
```

#### 方案 C：智能截断（保底）

```python
def _apply_convert_to_bullets(self, slide: SlideSpec):
    if not applied and len(summary) > 80:
        # ✅ 至少按句子边界截断
        summary = self._safe_truncate(summary, max_length=80)
        # 并警告用户
        self._add_warning("摘要已自动压缩，请检查语义完整性")

def _safe_truncate(self, text: str, max_length: int) -> str:
    """智能截断：优先在句子边界、逗号、空格"""
    if len(text) <= max_length:
        return text
    
    # 尝试在句子边界截断
    for delimiter in ["。", "；", "，", "、", " "]:
        idx = text.rfind(delimiter, 0, max_length - 1)
        if idx > max_length * 0.7:  # 至少保留 70%
            return text[:idx + 1].rstrip() + "…"
    
    # 实在不行，至少按词边界
    return text[:max_length - 1].rstrip() + "…"
```

### 问题 2 的正确方案

#### 方案 A：LLM 评估重要性（推荐）

```python
def _apply_promote_key_message(self, slide: SlideSpec):
    if updated.key_points:
        if self._llm:
            # ✅ 使用 LLM 识别最重要的要点
            promoted = self._llm_select_key_point(
                title=updated.title,
                message=updated.message,
                points=updated.key_points,
            )
        else:
            # 回退：让用户选择
            raise WorkflowError(
                "请选择要突出的核心信息。\n"
                f"候选：\n" + "\n".join(f"{i+1}. {p}" for i, p in enumerate(updated.key_points))
            )
```

#### 方案 B：启发式评分（次选）

```python
def _apply_promote_key_message(self, slide: SlideSpec):
    if updated.key_points:
        # ✅ 基于多个维度评分
        scored = []
        for point in updated.key_points:
            score = self._calculate_importance_score(point, updated.title)
            scored.append((score, point))
        
        promoted = max(scored, key=lambda x: x[0])[1]

def _calculate_importance_score(self, point: str, title: str) -> float:
    """多维度评分"""
    score = 0.0
    
    # 1. 关键词匹配（与标题相关）
    title_words = set(title.lower().split())
    point_words = set(point.lower().split())
    overlap = len(title_words & point_words)
    score += overlap * 2.0
    
    # 2. 位置权重（第一个和最后一个要点通常更重要）
    # （在调用处传入 index）
    
    # 3. 结论性关键词
    conclusion_keywords = ["总结", "结论", "因此", "所以", "核心", "关键", "ROI", "收益"]
    for keyword in conclusion_keywords:
        if keyword in point:
            score += 5.0
    
    # 4. 数据密度（包含数字可能更重要）
    import re
        if re.search(r'\d+%|\d+倍|增长|降低|提升', point):
        score += 3.0
    
    # 5. 长度惩罚（不应过度青睐长文本，但也不忽视）
    # 中等长度最优
    ideal_length = 30
    length_penalty = abs(len(point) - ideal_length) / ideal_length
    score -= length_penalty
    
    return score
```

#### 方案 C：交互式选择（保底）

```python
def _apply_promote_key_message_interactive(
    self, 
    slide: SlideSpec,
    selected_index: int | None = None
):
    """需要 UI 支持"""
    if selected_index is None:
        # 返回候选列表，让 UI 显示选择器
        return {
            "action": "select_key_point",
            "candidates": updated.key_points,
        }
    else:
        # 用户已选择
        promoted = updated.key_points[selected_index]
        # ... 继续处理
```

---

## 建议的改进优先级

### P0 - 立即修复（安全性）

1. **移除硬截断** - 改为抛出错误或使用安全截断
   - 风险：CRITICAL
   - 工作量：1 小时
   - 影响：避免数据损坏

### P1 - 短期改进（1-2 周）

2. **实现智能截断** - 至少按句子/词边界截断
   - 风险：HIGH → LOW
   - 工作量：2-4 小时

3. **添加用户警告** - 当自动处理不完美时通知用户
   - 工作量：1-2 小时

### P2 - 中期改进（1 个月）

4. **集成 LLM 压缩** - 用于摘要生成
   - 准确性：60% → 90%
   - 工作量：1-2 天

5. **实现启发式评分** - 改进要点选择
   - 准确性：40% → 70%
   - 工作量：1 天

### P3 - 长期改进（3 个月）

6. **LLM 要点评估** - 理解语义重要性
   - 准确性：40% → 95%
   - 工作量：2-3 天

7. **交互式确认** - UI 支持用户选择
   - 工作量：3-5 天（需要前端配合）

---

## 总结

### 当前问题

1. **硬截断** - 可能破坏语义、数值、专有名词
2. **最长选择** - 启发式不可靠，容易选错

### 核心原则

- ✅ **安全第一** - 不能静默破坏内容
- ✅ **用户知情** - 不确定时让用户决策
- ✅ **渐进降级** - 提供多个后备方案

### 下一步

1. 立即移除硬截断（替换为抛出错误）
2. 实现安全截断作为临时方案
3. 规划 LLM 集成路线图
