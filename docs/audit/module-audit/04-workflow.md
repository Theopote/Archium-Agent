# 04 — Workflow

模块：LangGraph 工作流 / 审批 / 恢复  
前缀：`WF-`  
更新：2026-07-26（含 WF-009 设计循环；WF-010 产品闭环）

| 编号 | 严重级别 | 状态 | 问题 | 文件 | 影响 | 修复方案 | 验收标准 | 提交 SHA |
|------|----------|------|------|------|------|----------|----------|----------|
| WF-001 | P0 | done | DeliverablePlan 审批在选择变更后未失效 | `deliverable_planning_service.py` | 过期计划仍可继续 | 选择变更使 approval 失效 | 变更后不可 resume 过期计划 | `-` |
| WF-002 | P0 | done | 共享 Sqlite checkpoint + 后台 continue 竞态 (W2) | `archium/workflow/checkpointer.py`; workflow services; background runner | 状态损坏 / 丢写 | `serialized_execution` 全局 DB 锁 + 同 run 互斥；共享 manager 不误关；后台拒绝重复 continue | 并发压测无脏写；`test_checkpointer_serialization` | `-` |
| WF-003 | P1 | done | `require_*_review` 对 brief/storyline 未真正暂停 | `pause_for_review` 相关 | 跳过人工审阅 | 尊重配置中断 | 配置开时图在对应节点 pause | `-` |
| WF-004 | P1 | done | 非 interrupt 的 `resume()` 可能从 START 重跑 (W3) | `resume_policy`; P/V/Pres `resume()` | 重复副作用 | resume 仅接 checkpoint；否则显式报错 | 无 interrupt 时 resume 失败而非重跑 | WF-004 |
| WF-005 | P1 | open | Route GENERATE_FROM_PROJECT vs bypass 分叉 (W4) | route dispatch | 路径不可预期 | 单一路由表 + 测试 | 每 route 有显式节点序列断言 | `-` |
| WF-006 | P1 | done | Plan 审批缺内容哈希 (W5) | DeliverablePlan `approval_hash`；`deliverable_plan_approval_hash` | 内容被改仍算已批 | 写入 content hash；变更作废 | hash 变则 approval 空 | WF-006 |
| WF-007 | P2 | open | 死 STEP_LABELS / 路由表残留 (W6) | workflow | 误导维护者 | 删除或生成自图定义 | 无死常量 | `-` |
| WF-008 | P0 | done | Golden 未覆盖 interrupt + continue_after_review（Beta B7） | `tests/golden/regression/test_interrupt_continue.py` | 主链回归不足 | case_a brief 门禁 interrupt → approve → continue | B7 关闭；golden regression 绿 | `-` |
| WF-009 | P2 | done | 设计循环非一等图节点（无 critique→human→revise→re-critique） | exploration/mission select；life-system 04 | 循环挂服务调用，难 interrupt | L2 Ask `pending_revise` 作为人闸 interrupt（不新 Agent/图） | Ask 可暂停；Apply/Reject 后继续 | `-` |
| WF-010 | P2 | done | OrchestrationPlan 与 product_flow 双轨；缺单一 stage truth | `product_stage_truth.py`; progress snapshot | 用户看到两套进度 | 编排 stage 映射进五阶段 | 主 chrome 只呈现一套当前阶段 | Topic 07 WF-010 |
