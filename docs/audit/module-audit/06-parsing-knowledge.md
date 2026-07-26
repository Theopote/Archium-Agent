# 06 — Parsing / knowledge

模块：文档解析与事实 / 知识库  
前缀：`KN-`  
更新：2026-07-26（含第二轮知识模型 Issue）

相关：[第二轮-02 建筑知识模型](../life-system/02-knowledge-model.md)

| 编号 | 严重级别 | 状态 | 问题 | 文件 | 影响 | 修复方案 | 验收标准 | 提交 SHA |
|------|----------|------|------|------|------|----------|----------|----------|
| KN-000 | P0 | done | 假目录冲突；伪造 citation UUID | fact validation; citation_from_draft | 错误冲突 / 坏引用 | 校验修复；禁止假 UUID | 相关单测绿 | `-` |
| KN-001 | P0 | done | 事实主键冲突丢弃 alternate 值 (K1) | `uq_fact_project_key`; fact 写入 | 真冲突被静默吞 | `alternate_values` 保留冲突备选值 | `test_upsert_retains_alternate_value_on_key_conflict` | `-` |
| KN-002 | P1 | open | Fact/Knowledge/Manuscript 有损桥接 (K2) | knowledge services | 信息丢失 | 显式映射 + 丢字段告警 | 往返字段清单测试 | `-` |
| KN-003 | P1 | open | 导出绕过 `filter_generation_facts` (K3) | `pptxgen_renderer` | 未审事实进稿 | 导出前统一过滤 | 过滤关则导出缺事实 / 开则一致 | `-` |
| KN-004 | P1 | open | LLM 任意键写入事实 (K4) | parsing/extraction | schema 污染 | 白名单键 | 未知键拒绝或进 quarantine | `-` |
| KN-005 | P1 | mitigated | 重解析与 `needs_ocr` 行为不清 (K5/K6) | `ingestion_service` OCR；`ocr_text.py`; `document_ocr_enabled` | 重复/漏 OCR | M1：needs_ocr→ocr_text；成功则 COMPLETED；重解析删块重建 | OCR 标志可测；无引擎时保持 needs_ocr | `-` |
| KN-006 | P2 | open | DOCX 页码语义弱；CitationORM 死 (K7/K8) | documents; models | 引用不准 | 页映射策略；删死表 | 页码断言 + 无死 ORM | `-` |
| KN-007 | P0 | done | Golden 缺事实账本 + review issues（Beta B9） | golden assertions / case_a | 主链质量不可见 | Ledger 计数 + CONFLICTED 状态 + review issue 下限 | B9 关闭；case_a 断言绿 | `-` |
| KN-008 | P1 | done | DesignKnowledge 与 ArchitectureCase 槽位不对齐（缺 problem/strategy；无 precedent 链接） | `design_knowledge.py`; `architecture_case.py`; `design_knowledge_mapping.py` | 研究写回与案例库两套词表；无法追溯先例 | 对齐字段 + `precedent_ref`；映射表单测 | Case↔DK 往返不丢 problem/strategy；可挂 `case:*` | `-` |
| KN-009 | P1 | done | ConceptDirection.reference_dna 无 case_id，无法回链案例库 | `concept_direction.py`; concept prompts | 参照基因不可验证、不可检索 | 增 `reference_case_ids`；dna 并存一期 | 选定方向可解析到 ArchitectureCase | `-` |
| KN-010 | P1 | done | ArchitectureCase 仅内存 8 seeds，不可持久/扩展 | `case_library/seeds.py`; `architecture_case_library.py`; `architecture_cases` 表 | 护城河无法随事务所增长 | 可写 Case 存储（项目级）+ seeds bootstrap | 可新增案例并参与 match；seeds 仍可用 | `-` |
| KN-011 | P2 | done | KnowledgeGraphSnapshot 只读时投影，无确认边持久化 | `knowledge_graph.py`; `knowledge_graph_edges` 表; `knowledge_graph_service.py` | 知识结构不积累 | 确认边表 + snapshot 合并；研究确认写 INSPIRED_BY/LINKED_FACT | 确认边重启后仍在；检索可走确认边 | `-` |
| KN-012 | P1 | done | Evidence 多身份未收敛（设计 vs 汇报） | `evidence_authority.py`; Presentation*/Materials* 别名 | 追溯断裂；命名污染设计知识 | 设计链权威 IntentEvidence+Citation；汇报 Evidence* 隔离命名 | 架构文列出权威；跨层引用有 ID | `-` |
| KN-013 | P2 | done | Case→DK 映射将 design_problem 塞进 insight，丢失独立性 | `architecture_case.to_design_knowledge` | 问题与洞察混淆 | DK 增 problem 或显式契约字段 | to_design_knowledge 保留 problem 槽 | `-` |
