# 12 — QA / delivery

模块：自动审查、导出门禁、人工验收  
前缀：`QD-`  
更新：2026-07-23

| 编号 | 严重级别 | 状态 | 问题 | 文件 | 影响 | 修复方案 | 验收标准 | 提交 SHA |
|------|----------|------|------|------|------|----------|----------|----------|
| QD-001 | P0 | done | qa_status / severity / 导出码 / IMAGE_NOT_LOADED 不一致 | review; deck QA; readiness | 门禁误放/误拦 | 统一映射与目录 | 导出门禁单测 + 合同 | `-` |
| QD-002 | P1 | open | Critic/DeckQA 默认不挡正式导出 | settings / export gate | 带伤交付 | 发布配置默认阻断 critical | RC 配置下 critical 不可导出 | `-` |
| QD-003 | P1 | open | Accept 只拦 *新* blocker | proposal accept | 旧 blocker 残留仍接受 | accept 扫全量 open blockers | 有 open blocker 不可 accept | `-` |
| QD-004 | P1 | open | `block_export_on_critical_review` 默认 False vs Studio 硬闸 | settings | 路径不一致 | 对齐默认与文档 | 两路径同策略 | `-` |
| QD-005 | P1 | open | Round-trip BLOCKED 写后不回滚 | delivery | 半写入 | 失败回滚或暂存 | BLOCKED 无半成品 | `-` |
| QD-006 | P0 | done | Repair → 清 issue → 再审（Beta B8）未闭环 | repair / review / golden | 修完仍脏 | 路由含 auto_fixable；repair 后 `resolve_open_for_presentation`；四层重入 + 轮次上限 | B8 关闭；`test_repair_rereview*` 绿 | `-` |
| QD-010 | P0 | open | 正式人工视觉门禁失败 / 未扩样 | `docs/QUALITY_GATE_STATUS.md` | 不能宣称视觉合格 | 真人 review + 扩至约定样本量 | QGS human 项 Passed | `-` |
