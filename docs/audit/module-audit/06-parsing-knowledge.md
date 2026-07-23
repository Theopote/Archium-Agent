# 06 — Parsing / knowledge

模块：文档解析与事实 / 知识库  
前缀：`KN-`  
更新：2026-07-23

| 编号 | 严重级别 | 状态 | 问题 | 文件 | 影响 | 修复方案 | 验收标准 | 提交 SHA |
|------|----------|------|------|------|------|----------|----------|----------|
| KN-000 | P0 | done | 假目录冲突；伪造 citation UUID | fact validation; citation_from_draft | 错误冲突 / 坏引用 | 校验修复；禁止假 UUID | 相关单测绿 | `-` |
| KN-001 | P0 | done | 事实主键冲突丢弃 alternate 值 (K1) | `uq_fact_project_key`; fact 写入 | 真冲突被静默吞 | `alternate_values` 保留冲突备选值 | `test_upsert_retains_alternate_value_on_key_conflict` | `-` |
| KN-002 | P1 | open | Fact/Knowledge/Manuscript 有损桥接 (K2) | knowledge services | 信息丢失 | 显式映射 + 丢字段告警 | 往返字段清单测试 | `-` |
| KN-003 | P1 | open | 导出绕过 `filter_generation_facts` (K3) | `pptxgen_renderer` | 未审事实进稿 | 导出前统一过滤 | 过滤关则导出缺事实 / 开则一致 | `-` |
| KN-004 | P1 | open | LLM 任意键写入事实 (K4) | parsing/extraction | schema 污染 | 白名单键 | 未知键拒绝或进 quarantine | `-` |
| KN-005 | P1 | open | 重解析与 `needs_ocr` 行为不清 (K5/K6) | parsers | 重复/漏 OCR | 状态机 + 文档 | 重跑幂等；OCR 标志可测 | `-` |
| KN-006 | P2 | open | DOCX 页码语义弱；CitationORM 死 (K7/K8) | documents; models | 引用不准 | 页映射策略；删死表 | 页码断言 + 无死 ORM | `-` |
| KN-007 | P0 | done | Golden 缺事实账本 + review issues（Beta B9） | golden assertions / case_a | 主链质量不可见 | Ledger 计数 + CONFLICTED 状态 + review issue 下限 | B9 关闭；case_a 断言绿 | `-` |
