**Batch 8（Visual Planning）已完成 P0。**

### 已修
1. **容量警告透传**：`format_layout_decision_warnings` 会输出 `CAPACITY.*`；`CAPACITY.IMPOSSIBLE` 经 `capacity_blocker_messages` 写入 workflow `errors`，不再静默空候选。
2. **DesignBrief → Intent**：已批准 / 待确认 brief 从当前 outline 载入，注入 `generate_for_slide`（family、density、资产、图面策略、任务/结论）。
3. **词汇对齐**：`photo_evidence_grid` 等归一为 `evidence_board`；brief density `low|medium|high` → intent `spacious|balanced|compact`。
4. **Repair 容量**：重估时传入 `visual_intent`。

相关测试 7 通过；`docs/architecture/current-system.md` 已同步。

### Backlog（未做）
- OVERLOADED 仍继续出候选（仅警告 + 禁缩字）
- Brief 未批准时 Intent 仍可独立生成
- `SlideDesignBrief.layout_family` 仍是自由字符串（靠别名表）
- DesignBrief 与 Layout 决策 LLM 双通道可能冲突
- Split / asset matching 与 capacity 的更深耦合

说「继续」进入 **Batch 9 RenderScene**。