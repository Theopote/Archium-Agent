## 批次 6 Parsing / Knowledge：结论

解析/分块基础可用；主要问题在**事实冲突语义错误**与**引用伪造**。

### 本轮已修（P0）

| 项 | 动作 |
|----|------|
| 假冲突 | 移除 catalog 里 `site_area`/`building_area` 等同组误报；`conflict_group` 仅在真实冲突时写入（`alias:`/`key:`/`empty:`） |
| 冲突计数 | `conflict_count` 只计 `CONFLICTED` 状态 |
| 引用伪造 | `citation_from_draft` 无法解析文档时返回 `None`，不再 `uuid4()` 造 id |

相关单测 9 passed。

---

### 管道结构

```text
文件 → document_parsers/* → ParsedDocument
     → IngestionService（分块/资产/向量/规则抽取）
     → FactExtractionService（规则 + LLM）
     → FactValidationService
     → FactLedger / ProjectKnowledge → Manuscript
```

---

### 剩余 backlog

| ID | 级 | 问题 |
|----|----|------|
| K1 | P0 | 同 key 冲突时备选值被丢弃（`uq_fact_project_key` 只留一行） |
| K2 | P1 | 三模型桥接：`ProjectFact` / `ProjectKnowledgeItem` / `ManuscriptFact` 转换有损 |
| K3 | P1 | 导出/渲染绕过 `filter_generation_facts`（`pptxgen_renderer` 直读 repo） |
| K4 | P1 | LLM 抽取接受任意 key，未对齐 `STANDARD_FACT_KEYS` |
| K5 | P1 | reparse 清 chunk 不 invalidate 关联 fact/citation |
| K6 | P1 | PDF `needs_ocr` 无后续 OCR 管线 |
| K7 | P2 | DOCX 无页码；语义 merge 丢 provenance |
| K8 | P2 | `CitationORM` 疑似死表；`safe_parse()` 未使用 |

---

### 健康点

- 五类 parser 统一 `ParsedDocument` 协议
- 规则 metric 抽取 + XLSX 单测扎实
- Domain 无 parser 依赖
- `knowledge_isolation` 策略清晰（调用方遵守时有效）
- 工作流 `build_from_project_research` 路径正确

---

下一步按总表是 **批次 7 Mission / Storyline**。需要的话直接继续。

[REDACTED]