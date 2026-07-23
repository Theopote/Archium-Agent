# 02 — Domain

模块：领域模型与分层边界  
前缀：`DOM-`  
更新：2026-07-23（含逐文件检查）

相关：[第一轮判断](00-round1-judgment.md)

## 检查结论摘要

| 检查项 | 结果 |
|--------|------|
| Domain → Application / Infrastructure / UI | **通过**（0 命中）；守卫见 `tests/unit/test_domain_layering.py` |
| Domain → sqlalchemy / streamlit / chromadb | **通过**（0 命中）；守卫已加强 |
| ORM 边界 | Domain 无 ORM import；仅有 `from_attributes` / 文档性「persisted」表述 |
| `domain/visual` 体量 | **约 52 文件 / ~7.2k LOC**，偏膨胀；QA/主题多套并存 |
| 空间 SSOT | **P0**：LayoutPlan.elements 与 RenderScene.nodes 双持几何 |
| 结构化数据 | Chart/Table 在 Spec / Layout / Scene **三份拷贝** |
| 同义枚举 | Severity ≥4；页类型/布局族/密度/叙事角色多套 |
| Service 逻辑在 Domain | NL parser、style resolve、pptx payload 工厂等仍在 domain |

包结构：根模块约 61 个 `.py` + `visual/` 52；非多级子包。超大非 visual 文件：`enums.py`（~668）、`powerpoint_capability.py`（~420）。

---

## Issue 台账

| 编号 | 严重级别 | 状态 | 问题 | 文件 | 影响 | 修复方案 | 验收标准 | 提交 SHA |
|------|----------|------|------|------|------|----------|----------|----------|
| DOM-001 | P0 | done | Domain 内含解析器实现（分层违规） | `archium/domain/`; parsers 迁出后 | Domain 依赖 IO | 解析迁 application；守卫 | domain layering 绿 | `-` |
| DOM-002 | P0 | done | `scene_semantic_qa` 分叉残留 | `visual/scene_semantic_qa.py` | 双份语义 QA | 删除分叉 | 文件不存在；`scene_qa.py` 在 | `-` |
| DOM-003 | P1 | open | `PresentationSpec` 与 `RenderScene`/`SlideSpec` 并存作导出真相 (D3) | `presentation_spec.py`; `slide.py`; `visual/render_scene.py` | 双/三 SSOT | Scene 为渲染 SSOT；Spec 派生或冻结 | 正式交付只认 Scene；文档一致 | `-` |
| DOM-004 | P1 | open | Severity 词汇表 ≥4 套 (D4) | `enums.py` ReviewSeverity/ValidationSeverity; `visual/enums.py` LayoutIssueSeverity; `page_quality.py` IssueSeverity | 门禁语义混乱 | 统一 catalog + 映射 | 导出门禁只认一套 | `-` |
| DOM-005 | P1 | open | 页类型枚举重叠 (D5) | `SlideType`; `FunctionalSlideType`; `TemplatePageType`; SpecSlide.layout str | 规划/渲染错配 | 收敛或显式映射表 | 无隐式互转 | `-` |
| DOM-006 | P1 | open | `SlideDesignBrief.layout_family` 等为自由字符串 (D6) | `slide_design_brief.py`; SpecSlide.layout; RenderScene.source_layout_family | 无法校验 | 受控词表/`LayoutFamily` | 非法 family 拒绝 | `-` |
| DOM-007 | P1 | open | `WorkflowStep` 过大耦合 (D7) | `enums.py` | 难演进 | 拆分阶段枚举 | 图定义不依赖巨枚举 | `-` |
| DOM-008 | P1 | open | Fact 三模型弱关联 (D8) | `fact.py`; `project_knowledge.py`; `presentation_manuscript.py` | 引用断裂 | 显式 ID 链接 + 不变量 | 跨模型可追溯 | `-` |
| DOM-009 | P2 | open | 审批/提案状态克隆 (D9) | `ApprovalStatus` vs `BriefStatus`; `ProposalStatus` vs `ThemeProposalStatus` | 状态漂移 | 合并或 1:1 映射 | 单一状态机文档 | `-` |
| DOM-010 | P2 | open | Chart/Table series 深拷贝语义不清 (D10) | Spec/Layout/Scene chart-table | 静默丢字段 | 明确 copy + 测试 | 变更不丢系列字段 | `-` |
| DOM-011 | P0 | done | **双空间 SSOT**：LayoutPlan 与 RenderScene 均持 x/y/w/h/z/lock | `visual/layout.py`; `studio_scene_service.py`; `studio_scene_edit_service.py` | Studio 改 Scene 后 Plan 静默漂移 / ensure 覆盖编辑 | `geometry_authority` + sync 切 `render_scene`；ensure 非 force 不覆盖；layout refresh 收回权威 | 合同 + `test_ensure_scene_preserves_render_scene_geometry_authority` | `-` |
| DOM-012 | P1 | open | Chart/Table **三份字段拷贝** | `presentation_spec.py`; `layout.py`; `render_scene.py` | 改一漏二 | 单一结构化数据类型；其余投影 | 一处修改三处一致的测试或单类型 | `-` |
| DOM-013 | P1 | open | 主张/要点链无类型化链接 | SlideIntent → Brief → SlideSpec → SpecSlide 平行字符串 | 文案漂移 | 单一内容 SSOT + FK | 改 claim 可追溯下游 | `-` |
| DOM-014 | P1 | open | Domain 内仍有 parser/resolver/导出工厂 | `edit_intent.py`; `content_adaptation.py`; `text_style.py`; `pptx_structure.py`; `slide_design_brief.py` | 分层回潮 | 迁 application；domain 留 DTO | domain 无 NL parse / pptx payload | `-` |
| DOM-015 | P1 | open | 废弃 `asset_path` 仍与 `storage_uri` 双写 | `render_scene.py` nodes; SpecImagePlacement | 可移植性与 schema v2 拖延 | 只持久化 storage_uri；迁移读路径 | 新写入无 asset_path；读兼容一期 | `-` |
| DOM-016 | P1 | open | 同名异义 `VisualRequirement` | `slide.py`; `visual/architectural_content_schema.py` | 导入歧义、评审混淆 | 重命名其一（如 Slide vs Schema） | 全仓唯一类名 | `-` |
| DOM-017 | P1 | done | `PostRenderCheckCode` 双定义 | ~~`visual/post_render_qa.py`~~; `visual/scene_qa.py` | 枚举漂移 | 删除死模块；保留 `scene_qa` | `rg PostRenderCheckCode` 仅 scene_qa；服务导入不变 | `-` |
| DOM-018 | P1 | open | `enums.py` 巨型（~668 行） | `archium/domain/enums.py` | 难审难演进 | 按限界上下文拆分 | 单文件可维护；无环依赖 | `-` |
| DOM-019 | P2 | open | 密度/叙事/角色等同义枚举丛 | DensityLevel vs expected_density vs PageDensityToken; NarrativeStage vs ContinuityRole vs PacingRole; ImageFit 多 Literal | 映射错误 | 映射表或收敛 | 文档列出唯一权威枚举 | `-` |
| DOM-020 | P2 | open | Overflow 词表不一致 | Layout `OverflowPolicy` vs TextNode Literal（含 `error` vs `warn`） | QA/渲染行为分歧 | 对齐词表 + 合同 | arch-contract 与节点 Literal 一致 | `-` |
| DOM-021 | P2 | open | `RenderResult` 持 Path、legacy marp 字段 | `render.py` | Domain 沾文件系统 | 迁 application DTO | domain 无业务 Path 聚合 | `-` |
| DOM-022 | P2 | open | `powerpoint_capability.py` 过大（~420） | 同文件 | 能力表难维护 | 拆分或数据驱动 | 单文件下降 | `-` |

---

## 逐文件检查记录（2026-07-23）

### 分层与 ORM

- 扫描 `archium/domain/**/*.py`：无 `archium.application|infrastructure|ui`、无 `sqlalchemy|streamlit|chromadb`。
- 无 ORM 模型 import；`_base.py` 的 `from_attributes=True` 可接受。
- 守卫：`test_domain_does_not_import_outer_layers`；已扩展第三方禁令。

### `visual/` 膨胀与 QA 栈

并存：`validation`、`critic`、`deck_qa`、`scene_qa`、`post_render_qa`、`page_quality`、`quality_issue_catalog`、根 `slide_semantic_qa` / `visual_qa`。主题：`DesignSystem` + `ThemeTokens` + `DeckThemeTokens`。登记在 DOM-004 / DOM-017 与 APP-004（应用层编排），Domain 侧先消重复枚举与双定义。

### 字段重叠（RenderScene / LayoutPlan / SlideSpec）

共享或近义：`slide_id`、`page_width/height`、`design_system_id`、`layout_plan_id`、`visual_intent_id`、`layout_family`/`source_layout_family`、元素几何、`fit_mode`、`overflow_policy`、chart/table 载荷、title/message/bullets。详见 DOM-011…013。

### Compatibility / 废弃字段（抽样）

| 位置 | 字段 |
|------|------|
| `render_scene.py` | `asset_path` ←→ `storage_uri`；`resolved_path` runtime-only |
| `architectural_content_schema.py` | `slide_purpose` ↔ `page_purpose`；legacy hydrate |
| `page_quality.py` | `ScoringMode.LEGACY_FORMAL` |
| `render.py` | `marp_*_path` legacy |
| `fact_ledger.py` | deprecated `conflict_group` |
| `enums.py` | `SlideChangeSource = RevisionSource` 别名 |

### Service 逻辑仍在 Domain（抽样）

`edit_intent.parse_natural_language`、`content_adaptation.suggest_content_adaptations`、`text_style.resolve_*`、`pptx_structure.to_pptxgen_payload` / `default_archium_structure_spec`、`slide_design_brief.infer_primary_visual_type` → **DOM-014**。

### 非 visual 重复

| 项 | 文件 |
|----|------|
| `VisualRequirement`×2 | `slide.py` / `architectural_content_schema.py` |
| `BriefStatus` ≈ `ApprovalStatus` | `slide_design_brief.py` / `enums.py` |
| Presentation vs PresentationSpec | `presentation.py`+`slide.py` / `presentation_spec.py` |

---

## 建议修复顺序（Domain）

1. ~~**DOM-011**（空间 SSOT）~~ **done**  
2. ~~**DOM-017**~~ **done**（删 `post_render_qa.py`）  
3. **DOM-016** — `VisualRequirement` 消歧  
4. **DOM-012** / **DOM-015** — 数据拷贝与 URI  
5. **DOM-004** / **DOM-020** — 门禁词表  
6. **DOM-014** — 迁出 parser（可分 PR）  
7. **DOM-018** — 拆 `enums.py`（机械重构）

逐文件明细：[02-domain-file-audit.md](02-domain-file-audit.md) · 第一阶段验收：[00-phase1-acceptance-2026-07-23.md](00-phase1-acceptance-2026-07-23.md)
