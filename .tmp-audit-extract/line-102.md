## 批次 7 Mission / Storyline：结论

规划门禁较成熟；主风险是 **Mission 身份在汇报交接处丢失**，以及 **审批失效不对称**。

### 本轮已修

| 项 | 动作 |
|----|------|
| P0 工作路径改选 | `select/deselect/set_workstream_selection` 会使已批准 DeliverablePlan → `DRAFT` |
| P0 陈旧 draft | `get_presentation_bridge` 仅在 live plan 仍为 `APPROVED` 时复用 draft |
| P1 未批准计划建汇报 | `build_presentation_request_for_mission` 必须有已批准 plan |
| P1 澄清写回 | 回答/假设/缺口会 `invalidate_approval()`；修订走同一路径并清 hash |
| P0 叙事模式绑定 | Storyline 优先经 `PlanningSession.presentation_id → current_mission_id` 取 mode |
| P1 再生成孤儿 | Mission regenerate 同时删除 workstreams **和** deliverable plans |

相关单测 31 passed。

---

### 结构

```text
Mission → 澄清 → 审批(hash)
  → Workstreams → DeliverablePlan → 审批
  → PresentationRequest → Brief → Storyline → Outline
```

---

### 剩余 backlog

| ID | 级 | 问题 |
|----|----|------|
| M1 | P1 | `Presentation` / `PresentationRequest` 仍无持久化 `mission_id`（仅靠 PlanningSession 回退） |
| M2 | P1 | `narrative_mode` 枚举 vs `Storyline.narrative_pattern` 自由字符串双轨 |
| M3 | P1 | Mode contract 未约束 Outline 阶段序列 |
| M4 | P1 | DeliverablePlan 仍无 content hash（弱于 Mission） |
| M5 | P2 | `EVIDENCE_ARGUMENT` / `PUBLIC_STORYTELLING` 从不被 suggest |
| M6 | P2 | `WorkstreamPlan` 域聚合几乎不落库 |
| M7 | P2 | OutlineApprovalRecord hash 仅审计、门禁不校验 |

---

### 健康点

- Mission `approval_hash` + 门禁校验扎实  
- 澄清就绪与 Mission 审批分离清晰  
- 非 PRESENTATION 交付物不会静默降级为 PPT  
- Workstream 只进生成上下文，不强迫成大纲章节  

---

下一步按总表是 **批次 8 Visual Planning**（DesignBrief、Layout、容量、拆页、素材匹配）。需要的话直接继续。