# Domain 逐文件审计（2026-07-23）

**范围：** `archium/domain/`（根 61 + `visual/` 原 52，本轮已删 1）  
**依据：** [第一阶段验收](00-phase1-acceptance-2026-07-23.md) · [台账](02-domain.md)  
**DOM-011：** 几何权威 **已关闭**（不重开）  
**本轮已执行：** 删除死模块 `visual/post_render_qa.py` → **DOM-017 done**

## 输出字段说明

| 字段 | 含义 |
|------|------|
| 裁决 | keep / delete / merge / refactor / relocate |
| 删除 | 是否删文件或符号 |
| 合并 | 是否并入他处 |
| 重构 | 是否改结构/拆分 |
| 方案 | 拟定改动 |
| 验收 | 可测通过条件 |

---

## A. 优先行动清单（按严重级别）

| 优先 | 编号 | 裁决 | 文件 | 一句话 |
|------|------|------|------|--------|
| 1 | DOM-017 | **done** | ~~`visual/post_render_qa.py`~~ | 死重复 `PostRenderCheckCode` 已删 |
| 2 | DOM-016 | **done** | `slide.py` + schema | `VisualRequirement` 消歧 |
| 3 | DOM-012 | **done** | `structured_payload.py` | Chart/Table 载荷单 VO |
| 4 | DOM-014 | **done** | edit_intent / brief / text / pptx catalog | parser/resolver/catalog 迁出 domain |
| 5 | DOM-004 | **done** | `visual/severity.py` | `IssueSeverity` 门禁权威 + 桥接 |
| 6 | DOM-003 | **done** | `export_authority` + Spec derived | 正式 PPTX 认 Scene |
| 7 | DOM-018 | **done** | `domain/enums/` 分包 | 按限界上下文拆分 |
| 8 | DOM-009 | **done** | Brief→`ApprovalStatus`；`proposal_status.ProposalStatus` | 审批/提案状态合一 |
| 9 | DOM-005 | **done** | `visual/page_type_catalog.py` | 页类型权威 + 显式交叉映射 |
| 10 | DOM-006 | **done** | `layout_family_normalize` + Brief/Scene | `LayoutFamily` 受控；非法拒绝 |
| 11 | DOM-007 | **done** | `enums/workflow_steps/` | 阶段枚举；图定义不依赖巨枚举 |
| 10 | DOM-006 | **done** | `visual/layout_family_normalize.py` | layout_family 受控词表；非法拒绝 |
| 11 | DOM-007 | **done** | `enums/workflow_steps/` | 阶段 WorkflowStep；图定义无巨枚举 |

职责边界（验收口径）：

| 对象 | 职责 |
|------|------|
| SlideSpec | 表达什么（内容主张） |
| LayoutPlan | 怎么排（编译期几何） |
| RenderScene | 怎么执行/编辑（渲染与 Studio SSOT） |

---

## B. 根模块 — 有问题项

### `enums/` package（DOM-018 done）

| 字段 | 内容 |
|------|------|
| 角色 | 全仓 StrEnum 分包 |
| 裁决 | **done** — `project/document/knowledge/presentation/mission/assets/review/workflow` |
| 级别 | P1 |
| 问题 | ~~巨型 monolith~~ |
| 方案 | 包级 re-export 保持 `archium.domain.enums` 导入；单文件 <250 |
| 验收 | `test_enums_package`；无 `enums.py` 单体 |

### `powerpoint_capability.py` (~420)

| 字段 | 内容 |
|------|------|
| 角色 | PPT 能力矩阵常量 |
| 裁决 | refactor |
| 级别 | P2 |
| 问题 | 过大；偏静态目录 |
| 删除 | 否 |
| 合并 | 否 |
| 重构 | 是 — 数据驱动或拆分 |
| 方案 | JSON/分模块；代码变薄 |
| 验收 | 能力查询行为不变；文件可维护 |

### `presentation_spec.py` (~100)

| 字段 | 内容 |
|------|------|
| 角色 | 遗留 Spec 导出模型（derived-only） |
| 裁决 | keep（兼容）/ freeze |
| 级别 | P1（DOM-003 **done**） |
| 问题 | ~~与 Scene 双真相~~；仍可用于模板 compat |
| 方案 | 正式交付禁 Spec 直出；`FormalPptxExportService` 优先 Scene |
| 验收 | arch-contract formal-export-authority；可编辑 PPTX 优先 Scene |

### `slide.py` (~107)

| 字段 | 内容 |
|------|------|
| 角色 | SlideSpec + VisualRequirement（页内容） |
| 裁决 | refactor |
| 级别 | P1（DOM-016） |
| 问题 | `VisualRequirement` 与 schema 同名异义 |
| 删除 | 否 |
| 合并 | 否 |
| 重构 | 是 — 重命名为 `SlideVisualRequirement` |
| 方案 | 全局改名 + 导入更新 |
| 验收 | 全仓唯一类名；mypy 绿 |

### `slide_design_brief.py`（模型 only；启发式已迁）

| 字段 | 内容 |
|------|------|
| 角色 | 设计 Brief 模型 + 策略默认值 |
| 裁决 | keep（模型）；~~infer/format/protection~~ → `application/slide_design_brief_heuristics.py` |
| 级别 | P1（DOM-014 **done**；DOM-006 **done**） |
| 问题 | ~~`layout_family` 自由字符串~~；~~BriefStatus / ThemeProposalStatus~~ 已合 |
| 方案 | family 经 `layout_family_normalize`；状态见 DOM-009 |
| 验收 | domain 无 layout 字符串启发式 |

### `content_adaptation.py`（DTO only；启发式已迁）

| 字段 | 内容 |
|------|------|
| 角色 | 内容适配动作枚举 + Suggestion DTO |
| 裁决 | keep（模型）；~~suggest/parse~~ → `application/content_adaptation_heuristics.py` |
| 级别 | P1（DOM-014 **slice done**） |
| 问题 | 曾含服务逻辑 |
| 方案 | 已迁；调用方改 application import |
| 验收 | domain 无 suggest/parse；相关单测绿 |

### `render.py` (~78)

| 字段 | 内容 |
|------|------|
| 角色 | RenderResult 路径聚合 |
| 裁决 | relocate |
| 级别 | P2（DOM-021） |
| 问题 | 持 `pathlib.Path`；legacy marp 字段 |
| 删除 | 否 |
| 合并 | 否 |
| 重构 | 迁 application DTO |
| 方案 | 新类型在 application；domain 停增长 |
| 验收 | 新代码不在 domain 扩 Path 结果 |

### `fact.py` / `project_knowledge.py` / `presentation_manuscript.py` / `citation.py`

| 字段 | 内容 |
|------|------|
| 角色 | 事实→知识→文稿链 |
| 裁决 | refactor |
| 级别 | P1（DOM-008） |
| 问题 | 弱关联；多套 citation 形状 |
| 删除 | 否 |
| 合并 | citation 类型收敛 |
| 重构 | 显式 FK + 不变量 |
| 方案 | 文档化链路；禁止第四套 claim 类型 |
| 验收 | 跨模型引用可测 |

### `slide_intent.py` (~96)

| 字段 | 内容 |
|------|------|
| 角色 | 页任务卡 |
| 裁决 | keep（与 Brief 边界文档化） |
| 级别 | P2 |
| 问题 | 与 Brief 平行字符串（主张链 DOM-013） |
| 删除 | 否 |
| 合并 | 否 |
| 重构 | 主张链加 FK |
| 方案 | 见 DOM-013 |
| 验收 | claim 变更可追溯 |

### `review.py` / `review_rules.py` / `visual_qa.py` / `slide_semantic_qa.py`

| 字段 | 内容 |
|------|------|
| 角色 | 审核与语义 QA 模型 |
| 裁决 | keep；severity 经桥接 |
| 级别 | P1（DOM-004 **done**） |
| 问题 | ~~多套 severity 无映射~~；QA 报告形状仍多样（APP） |
| 方案 | 门禁/导出经 `IssueSeverity`；`ReviewSeverity` 仅持久化 |
| 验收 | `export_gating` + `test_severity_bridge` |

### `deck_delivery.py` (~192)

| 字段 | 内容 |
|------|------|
| 角色 | 交付聚合 |
| 裁决 | relocate（`aggregate_*`）若含策略 |
| 级别 | P2 |
| 问题 | 聚合策略可下沉 application |
| 删除 | 否 |
| 合并 | 否 |
| 重构 | 薄 DTO |
| 方案 | 策略函数迁出 |
| 验收 | domain 仅模型 |

### `slide_recovery.py` (~242)

| 字段 | 内容 |
|------|------|
| 角色 | 页面复活领域模型 |
| 裁决 | keep |
| 级别 | none–P2 |
| 问题 | 体量偏大但角色清晰 |
| 删除 | 否 |
| 合并 | 否 |
| 重构 | 可选拆分 |
| 方案 | 维持；防塞入 IO |
| 验收 | 无 parser/IO 进入 |

### `workflow_route.py` / `workflow.py` / `planning_session.py` / `workstream.py` / `deliverable.py` / `project_mission.py` / `outline.py`

| 字段 | 内容 |
|------|------|
| 角色 | Mission/规划/工作流路由 |
| 裁决 | keep |
| 级别 | none–P2（WF-006 死常量另见 workflow 台账） |
| 问题 | 个别死标签在应用层 |
| 删除 | 否（domain 模型） |
| 合并 | 否 |
| 重构 | 否 |
| 方案 | 保持 |
| 验收 | 分层测试绿 |

---

## C. 根模块 — 保持（无强制动作）

| 文件 | ~LOC | 角色 | 裁决 |
|------|------|------|------|
| `_base.py` | 59 | Domain 基类 | keep |
| `__init__.py` | 134 | 导出 | keep（可收紧 `__all__`） |
| `project.py` | 35 | 项目 | keep |
| `document.py` | 63 | 文档 | keep |
| `asset.py` | 44 | 资产 | keep |
| `memory.py` | 22 | 记忆 | keep |
| `llm_profile.py` | 27 | LLM 配置 DTO | keep |
| `fallback_image.py` | 19 | 回退图 | keep |
| `studio_errors.py` | 23 | Studio 错误码 | keep |
| `revision.py` | 49 | 修订 | keep |
| `slide_history.py` | 44 | 页历史 | keep |
| `slide_repair.py` | 30 | 页修复 DTO | keep |
| `slide_generation_context.py` | 38 | 生成上下文 | keep |
| `slide_split.py` | 76 | 拆页 | keep |
| `slide_asset_binding.py` | 161 | 资产绑定 | keep |
| `page_pipeline_status.py` | 100 | 页管线状态 | keep |
| `outline_approval_record.py` | 27 | 大纲批准记录 | keep |
| `plan_overlay.py` | 86 | Plan 叠加元数据 | keep |
| `delivery_record.py` | 30 | 交付记录 | keep |
| `export_fidelity.py` | 197 | 导出保真策略 | keep |
| `export_round_trip.py` | 90 | 往返导出 | keep |
| `artifact_ownership.py` | 154 | 制品所有权 | keep |
| `knowledge_gap.py` | 158 | 知识缺口 | keep |
| `fact_ledger.py` | 47 | 事实账本策略 | keep（弃用字段见 DOM-015 类） |
| `narrative_arc.py` | 81 | 叙事弧 | keep |
| `architectural_narrative_mode.py` | 128 | 叙事模式 | keep |
| `cultural_narrative.py` | 117 | 文化叙事 | keep |
| `renovation_issue.py` | 81 | 更新议题 | keep |
| `reference_style.py` | 74 | 参考风格 | keep |
| `deck_coherence.py` | 39 | 整册连贯 | keep |
| `model_roles.py` | 111 | 模型角色 | keep |
| `pipeline_role_mapping.py` | 107 | 管线角色映射 | keep |
| `agent_skill.py` | 90 | Agent Skill | keep |
| `project_acceptance.py` | 139 | 项目验收 | keep |
| `scene_revision_summary.py` | 75 | Scene 修订摘要 | keep |
| `presentation.py` | 113 | Presentation/Brief/Storyline | keep |

---

## D. `visual/` — 有问题项

### ~~`post_render_qa.py`~~ — **已删除**

| 字段 | 内容 |
|------|------|
| 裁决 | delete **done** |
| 级别 | P0 → closed |
| 验收 | `scene_qa.PostRenderCheckCode` 唯一；服务仍从 `scene_qa` 导入 |

### `scene_qa.py` (~55)

| 字段 | 内容 |
|------|------|
| 角色 | 语义/post-render 检查码（现唯一） |
| 裁决 | keep |
| 级别 | none |
| 方案 | 保持唯一码表 |
| 验收 | 无第二份 PostRenderCheckCode |

### `layout.py` / `render_scene.py`

| 字段 | 内容 |
|------|------|
| 角色 | LayoutPlan；RenderScene |
| 裁决 | refactor（载荷）/ keep（几何权威 API） |
| 级别 | P1（DOM-012/015）；DOM-011 **done** |
| 问题 | Chart/Table 字段双拷；`asset_path` 双写；lock_scopes 类型不一致 |
| 删除 | 否 |
| 合并 | 共享 ChartData/TableData VO |
| 重构 | URI schema v2；typed locks |
| 方案 | 抽 VO；停止镜像 asset_path |
| 验收 | 一处改载荷；geometry_authority 行为不变 |

### `enums.py`（visual）/ `page_quality.py`

| 字段 | 内容 |
|------|------|
| 角色 | 布局枚举；门禁经 severity 桥 → IssueSeverity |
| 裁决 | keep + bridge via bridge |
| 级别 | P1（DOM-004 **done** / DOM-020 **done**） |
| 问题 | ~~多套 severity 无映射~~；~~overflow 词表~~ |
| 方案 | 门禁以 IssueSeverity 为准（`domain/visual/severity.py`） |
| 验收 | 导出门禁经桥接；`test_severity_bridge` |

### `edit_intent.py` / `parsed_intent.py` / `placeholder_binding.py` / `semantic_block.py`

| 字段 | 内容 |
|------|------|
| 裁决 | keep（枚举/DTO）；helpers → application |
| 级别 | P1（DOM-014 **done**） |
| 问题 | ~~NL / normalize / text_style~~ 已迁；`text_style.py` 已删 |
| 方案 | `nlp_parser` / `placeholder_binding_normalize` / `text_style_resolve` |
| 验收 | domain 无 keyword NL / OOXML normalize / resolve_* |

### `atomic_operation.py` / `studio_command.py` / `element_edit_intent.py` / `element_lock.py` / `slide_edit_command.py`

| 字段 | 内容 |
|------|------|
| 裁决 | merge / refactor |
| 级别 | P1 |
| 问题 | 多套编辑协议；`ElementEditOperation` 同名异义（Literal vs StrEnum） |
| 方案 | 命名消歧；文档化 Layout 事务 vs Studio 命令矩阵 |
| 验收 | 无歧义导入；路由表单测 |

### `pptx_structure.py`（模型 only；catalog 已迁）

| 字段 | 内容 |
|------|------|
| 裁决 | keep（Spec/枚举）；~~factories / payload~~ → `infrastructure/renderers/pptx_structure_catalog.py` |
| 级别 | P1（DOM-014 **done**） |
| 问题 | 曾含巨型默认目录 + `to_pptxgen_payload` |
| 方案 | 已迁；domain 仅图验证与 lookup |
| 验收 | domain 无 catalog 工厂；导出仍绿 |

### `style_binding.py` (~65)

| 字段 | 内容 |
|------|------|
| 裁决 | wire or delete |
| 级别 | P1 |
| 问题 | 生产未接线，仅单测 |
| 方案 | 接到 TextNode 或删除抽象 |
| 验收 | 无未用公共 API |

### `benchmark.py` / `e2e_benchmark.py`

| 字段 | 内容 |
|------|------|
| 裁决 | refactor |
| 级别 | P2 |
| 问题 | 过大；`E2EBenchmarkScenario(str)` 非真枚举 |
| 方案 | 拆分；改 StrEnum |
| 验收 | 类型安全；runner 不变 |

### QA 报告簇 `deck_qa` / `critic` / `validation`

| 字段 | 内容 |
|------|------|
| 裁决 | merge Finding 形状 |
| 级别 | P2 |
| 方案 | 公共 QaFinding + severity 桥 |
| 验收 | 字段一致 |

### `architectural_content_schema.py`

| 字段 | 内容 |
|------|------|
| 裁决 | refactor（改名 VisualRequirement） |
| 级别 | P1（DOM-016） |
| 方案 | `SchemaVisualRequirement` |
| 验收 | 与 slide 侧类名不冲突 |

### `__init__.py`（visual ~245）

| 字段 | 内容 |
|------|------|
| 裁决 | refactor |
| 级别 | P2 |
| 问题 | barrel 不完整/过大 |
| 方案 | 明确公开面或缩小 |
| 验收 | `__all__` = 文档公开 API |

---

## E. `visual/` — 保持

| 文件 | 角色 | 裁决 |
|------|------|------|
| `art_direction.py` | 整册视觉语言 | keep |
| `visual_intent.py` | 内容→布局桥 | keep |
| `preferences.py` / `scene_presets.py` | 偏好/预设 | keep |
| `deck_composition.py` | 节奏 | keep |
| `deck_repair.py` / `scene_repair.py` | 修复 DTO | keep |
| `icon_usage_policy.py` / `architectural_icon.py` | 图标 | keep |
| `template_match.py` / `template_usage_brief.py` | 模板匹配 | keep |
| `slide_capacity_budget.py` | 容量门禁 | keep |
| `partial_edit_preservation.py` | 局部编辑合同 | keep |
| `design_system.py` / `defaults.py` | 设计系统 | keep |
| `image_derivative.py` | 衍图合同 | keep |
| `quality_issue_catalog.py` | 问题目录 | keep |
| `scene_change_proposal.py` / `theme_change_proposal.py` | 提案 | keep（状态可合并） |
| `reference_slide*.py` | 参考页 | keep |
| `architectural_template.py` / `template_induction.py` | 模板归纳 | keep（分类枚举映射 P2） |
| `deck_theme_tokens.py` | 主题面板 token | keep（密度词对齐 P2） |
| `element_comment.py` | 评论 | keep（Literal 可去） |
| `slide_edit_snapshot.py` | 事务快照 | keep |

---

## F. 依赖方向（抽检结果）

| 检查 | 结果 |
|------|------|
| domain → application/infrastructure/ui | **0**（守卫通过） |
| domain → sqlalchemy/streamlit/chromadb | **0**（守卫通过） |
| ORM 表定义在 domain | **无** |

---

## G. 建议执行顺序（代码改动）

1. ~~DOM-017 删死模块~~ **done**  
2. ~~DOM-016~~ **done**  
3. ~~DOM-012~~ **done**  
4. ~~DOM-014~~ **done**  
5. ~~DOM-004~~ **done**（severity 桥）  
6. ~~DOM-009~~ **done**（提案共享 ProposalStatus）  
7. ~~DOM-003~~ **done**（正式 PPTX → Scene）  
8. ~~DOM-018~~ **done**（enums 分包）

台账同步：[02-domain.md](02-domain.md)
