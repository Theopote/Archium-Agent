**Batch 12（QA / Delivery）完成。**

### 已修
1. **`qa_status`**：blocker→`blocked`，major→`needs_review`（不再把 blocker 标成 pass）
2. **Dedupe**：同 code/evidence 保留最高 severity（图纸 COVER 不再被 MAJOR 盖掉）
3. **Review 严重度**：按 catalog 映射，TEXT_OVERFLOW 等不会因 finding 写 `medium` 而降级
4. **导出门控**：补齐 BLACK_BLOCK / IMAGE_NOT_LOADED / PNG_PPTX_DIFF / TEXT_OVERFLOW / STOCK 等
5. **Post-render**：截图缺失发出 `IMAGE_NOT_LOADED`，不再静默跳过
6. **DeckQA `blocker_count`**：CRITICAL/ERROR 可进入 readiness
7. **正式导出**：readiness 内存跑 Scene semantic BLOCKER（不刷 ReviewIssue）

相关测试 53 通过。

### Backlog
- Critic / DeckQA 仍默认不阻断正式导出
- Accept 只拦「新引入」blocker，存量 blocker 可过
- `block_export_on_critical_review` 默认 False（workflow）与 Studio 硬门不一致
- Round-trip BLOCKED 在 PPTX 写出之后才标，不回滚
- Slide vs Scene 检查码仍有重复/别名

说「继续」进入 **Batch 13 UI**。