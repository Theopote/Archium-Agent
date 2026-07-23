# 08 — Visual planning

模块：VisualIntent、LayoutPlan、容量与 brief  
前缀：`VP-`  
更新：2026-07-23

| 编号 | 严重级别 | 状态 | 问题 | 文件 | 影响 | 修复方案 | 验收标准 | 提交 SHA |
|------|----------|------|------|------|------|----------|----------|----------|
| VP-001 | P0 | done | 容量状态未驱动规划行为 | `layout_planning_service.py` | 不可排仍出候选 | CAPACITY 警告；IMPOSSIBLE 硬阻断 | 合同/单测：impossible 不产出可交付候选 | `-` |
| VP-002 | P0 | done | 已批 brief 未注入 VisualIntent；别名混乱 | visual planning | 风格/意图丢失 | 注入 + alias 规范化 | 有批 brief 时 Intent 字段一致 | `-` |
| VP-003 | P1 | open | OVERLOADED 仍排放候选 | capacity 逻辑 | 过载页进下游 | 策略：阻断或标 needs_split | 过载默认不进正式导出链 | `-` |
| VP-004 | P1 | open | 无已批 brief 仍可建 Intent | planning | 跳过审阅 | 配置门禁 | require brief 时拒绝 | `-` |
| VP-005 | P1 | done | layout_family 自由字符串（同 DOM-006） | `layout_family_normalize` | 无法校验 | 受控词表 | 非法拒绝 | `-` |
| VP-006 | P2 | open | Brief LLM 与 Layout LLM 冲突；split/asset 耦合 | visual services | 结果抖动 | 单一裁决规则 | 冲突可复现单测 | `-` |
