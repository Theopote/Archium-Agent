## 批次 2 Domain：结论

主链分层清晰（`SlideSpec → DesignBrief → VisualIntent → LayoutPlan → RenderScene`），**不要合并**这些层。真正的问题是：QA/严重度词汇分裂、双导出路径、以及少数 domain 越界。

### 本轮已修（P0）

1. **分层泄漏**：`llm_parser` / `hybrid_parser` / `EnhancedNLPParser` 迁到 `application/visual/`；domain 只留 `parsed_intent.py`（DTO）。
2. **死代码分叉**：删除 `scene_semantic_qa.py`（与 `scene_qa.py` 同名不同值）。
3. **守卫测试**：`tests/unit/test_domain_layering.py`（domain 不得 import 外层）。

相关单测 30 passed。

---

### 剩余 backlog（按优先级）

| ID | 级 | 问题 | 建议 |
|----|----|------|------|
| D3 | P1 | `PresentationSpec` 与 `RenderScene` 双导出 | 收敛到 Scene；Spec 仅作 infra 适配 |
| D4 | P1 | 严重度 ×4（`Review` / `Validation` / `LayoutIssue` / `Issue`） | 统一 canonical + 投影 |
| D5 | P1 | 页类型枚举重叠（`SlideType` / `FunctionalSlideType` / `TemplatePageType`…） | 分层 canonical + 显式映射表 |
| D6 | P1 | `SlideDesignBrief.layout_family: str` 等弱类型 | 绑到 `LayoutFamily` / `DensityLevel` |
| D7 | P1 | `WorkflowStep` 过大（~75 值，四管线合一） | 按 Planning/Presentation/Visual/Recovery 拆分 |
| D8 | P1 | Fact 三态（`ProjectFact` / Knowledge / Manuscript）弱联动 | 统一 verification + 晋升规则 |
| D9 | P2 | `ProposalStatus` ≈ `ThemeProposalStatus` | 合并或共享基类 |
| D10 | P2 | Chart/Table series 模型克隆 | 一处定义，适配器复用 |

### 健康点

- `DomainModel`（`extra=forbid` + assignment 校验）扎实  
- `SlideSpec` / `LayoutPlan` / `RenderScene` 有真实不变量  
- Brief 家族（Presentation / SlideDesign / TemplateUsage）是不同作用域，不是事故重复  
- 除已修解析器外，domain 无 Streamlit / SQLAlchemy 泄漏  

---

下一步建议：**批次 3 Application**，或先收 **D3+D4**（双导出与严重度）作为 Domain 收敛第二刀。你定方向即可。

[REDACTED]