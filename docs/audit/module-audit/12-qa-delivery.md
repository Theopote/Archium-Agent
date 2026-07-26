# 12 — QA / delivery

模块：自动审查、导出门禁、人工验收  
前缀：`QD-`  
更新：2026-07-23

| 编号 | 严重级别 | 状态 | 问题 | 文件 | 影响 | 修复方案 | 验收标准 | 提交 SHA |
|------|----------|------|------|------|------|----------|----------|----------|
| QD-001 | P0 | done | qa_status / severity / 导出码 / IMAGE_NOT_LOADED 不一致 | review; deck QA; readiness | 门禁误放/误拦 | 统一映射与目录 | 导出门禁单测 + 合同 | `-` |
| QD-002 | P1 | mitigated | Critic/DeckQA 默认不挡正式导出 | settings / export gate；APP-004 `ExportVerdict` | 带伤交付 | DeckQA blocker_count 计入导出门禁；Critic 仍以警告为主 | DeckQA 阻塞可挡导出；Critic 硬挡另议 | APP-004 |
| QD-003 | P1 | done | Accept 只拦 *新* blocker | `scene_proposal_qa.proposal_has_open_blocker`; accept_proposal | 旧 blocker 残留仍接受 | accept 扫全量 open blockers | 有 open blocker 不可 accept | QD-003 |
| QD-004 | P1 | done | `block_export_on_critical_review` 默认 False vs Studio 硬闸 | `settings.py` default=True；export_gate | 路径不一致 | 对齐默认与文档 | 两路径同策略 | 已对齐（默认 True） |
| QD-005 | P1 | open | Round-trip BLOCKED 写后不回滚 | delivery | 半写入 | 失败回滚或暂存 | BLOCKED 无半成品 | `-` |
| QD-006 | P0 | done | Repair → 清 issue → 再审（Beta B8）未闭环 | repair / review / golden | 修完仍脏 | 路由含 auto_fixable；repair 后 `resolve_open_for_presentation`；四层重入 + 轮次上限 | B8 关闭；`test_repair_rereview*` 绿 | `-` |
| QD-010 | P0 | open | 正式人工视觉门禁失败 / 未扩样 | `docs/QUALITY_GATE_STATUS.md` | 不能宣称视觉合格 | 真人 review + 扩至约定样本量 | QGS human 项 Passed | `-` |
