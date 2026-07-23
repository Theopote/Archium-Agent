# Visual Quality & Editing Sprint（视觉质量与编辑可用性冲刺）


> **文档状态：历史快照。**
> 本文记录特定阶段的分析、实施、验收或计划，可能包含已过时的路径、状态和结论。
> 当前行为以代码、测试、`README.md`、`docs/README.md` 及现行专题文档为准。
## 背景与定位
Archium（阿基姆）的瓶颈不是“生成更多内容”，而是让最终页面在建筑汇报场景里具备：

1. 专业的视觉语言（图标/符号、图文层级、节奏感）
2. 图片作为素材的统一观感（但不破坏证据真实性）
3. 稳定的“好看”衡量机制（截图级回归 + 指标分层）
4. 生成后的可编辑性（用户能把结果改到自己需要的样子）

本冲刺把你提出的 5 条建议收敛为一个闭环：  
**语义视觉语言 → 原生渲染支持 → Studio 编辑协议 → 截图视觉回归 → round-trip QA**。

## 当前现状（与本冲刺的关系）
本仓库已经存在多项“骨架能力”，因此本冲刺的目标是把它们收束到统一的视觉质量闭环，而不是从零堆能力清单。

- 图标语义注册：已存在 `ArchitecturalIcon` 与语义匹配测试（语义键 → 内置 SVG）。
- 图标 Embedding：离线 `embeddings.json` + `LocalLexicalEmbeddingProvider`（**不再**用 `MockEmbeddingProvider`）；query 向量在匹配循环外只算一次。
- Icon Usage Policy：每页上限、允许/禁止 LayoutFamily、置信度门槛、图纸/证据页禁用、超载/高密度移除图标。
- PPTX 图标：自带 SVG 包（非 Lucide npm）；`addImage` 保留 `.svg` 路径；CairoSVG 仅用于 PNG 预览栅格化。
- 字体度量：`TextMeasurementService` 默认走 Pillow FreeType（`ImageFont.truetype`→`getbbox`）；`FontManifest` 记录 requested/resolved/source_uri/file_hash/platform/fallback；视觉基线绑定 `font_manifest_hash`（同平台漂移先报字体变更）。校准见 `tests/unit/visual/test_font_manifest.py`。
- 截图级回归：明确双轨 — `preview_visual_regression`（Python wireframe）与 `pptx_visual_regression`（PPTX→LibreOffice）；基线更新走 candidate → 人工审核 → `approve-baseline`；V8–V9 / V14 图标已 CI 门禁，其余 V10–V18 builders + unit 覆盖（promote 后入 CI）。
- Studio 编辑协议：多选/直编/Undo 分支已落地；**评论 Inbox** 已挂 Studio「评论」页；Theme 接受前显示 **全稿影响统计**；拆页走 **SlideSplitProposal Before/After**；Skill 调用写入 `cache/skill_audits/`；浏览器验收清单见 `docs/roadmap/studio-browser-acceptance.md`。
- 图片智能处理 / ImageDerivative：**PARTIAL→增强** — Pillow：EXIF→sRGB、可调 unify（色温/饱和度/对比度）、启发式主体/天际线 focal crop、轻度 sharpen/denoise/historical_restore；证据/图纸 clamp；`ImageProcessor` 门面；**禁止** PptxGen 滤镜；模型级主体检测 / 生成式修复仍 deferred；≠ 页面复活 OCR/VLM

因此，本冲刺重点转向：**把图标、图片、版式变体带入统一的 RenderScene 节点/渲染路径，并让它们被视觉回归捕获；同时把 Studio 编辑补齐到可用的 V1 边界**。

## 非目标（明确边界）
在冲刺周期内不做以下工作，避免扩大不稳定面：
- 不做“完整 LLM 自动效果图生成 / 大规模 AI 修图”
- 不做“万能约束求解器一次性覆盖任意素材数量/比例”
- 不把所有图片无差别统一滤镜（证据照片需要严格区分处理模式）
- 不把截图回归要求所有页面做像素级完全一致（会采用分级容差与结构性阈值）

## 目标（可验收的输出）
交付物以“可自动抓住退化”的能力为准：

1. **IconNode + PPTX 矢量渲染**：语义图标可被选中、渲染为矢量（或保持 SVG 路径特性），且能被截图回归稳定捕获。
2. **ImageTreatmentSpec + Asset Derivative**：**PARTIAL+**（见 Sprint 3）。Pillow 衍生含启发式 focus、可调 unify、轻度 enhance；模型级主体检测 / AI 修复仍未做。
3. **Studio V1 可用编辑链**：拖拽/缩放/锁定/删除/对齐/撤销重做等操作都落到 `StudioCommand → ScenePatchAction → Revision`，而不是绕过命令链直接改前端状态。
4. **截图视觉回归基线扩展**：在现有 composition 基线之外，把关键组件（图标卡片、流程步骤、照片网格、决策/风险块等）纳入可维护的 baseline 体系。

## 冲刺总策略
先做“可衡量的基础设施”，再扩展视觉能力。优先级为：

1. **Icon & Font QA 基线**
2. **Studio 可用编辑 V1**
3. **Image 衍生与安全统一**
4. **Layout Family 参数化/变体扩展**
5. **更大范围 screenshot regression（组件 → 页面 → deck）**

### 原则：可用性优先于花哨
用户是否愿意采用，不取决于版式理论是否先进，而取决于生成结果能否方便改到位。

### 原则：真实性优先（证据照片保护）
任何颜色统一/裁切/滤镜都必须服从证据策略：证据类素材不允许被“改变表达”的后处理破坏。

### 原则：回归先于扩展
在每一轮新增视觉能力（图标、滤镜、裁切、variant）之前，先补齐它在测试中“会被抓到”的基线覆盖面。

## Sprint 1：Visual Foundation（图标 + 组件基线）
### 要做什么
1. 扩展图标领域模型到“注册表 + 节点可渲染”的层次：
   - 明确 Icon Registry（语义键 → SVG 资源路径）
   - 引入 `IconNode` 并在 RenderScene 中作为原生节点存在
2. 在 `archium/infrastructure/renderers/pptxgen/components/` 增加图标渲染组件：
   - 优先使用 SVG path data URI 的方式进入 PPTX 渲染层
   - 支持 `stroke/fill/opacity/strokeWidth` 等主题级可变参数
3. 扩展截图回归 baseline 覆盖关键语义组件：
   - `IconMetricCard`（指标卡：图标 + 数值 + 标签）
   - `ProcessStep`（流程步骤：箭头/阶段 + 文字）
   - `DecisionBlock` / `RiskBlock`（决策/风险：语义图标 + 文案）
### 验收指标（示例阈值，可在 PR 中具体化）
- 至少 30 个基础图标语义可用（能匹配并渲染）
- 至少 20 个建筑语义映射可落地（能在 IconSelection 中选中）
- 图标在 PPTX 中表现为矢量特性（至少不要求转成大面积 PNG 位图）
- 新增/更新的组件 baseline 在 CI 中通过截图回归（允许小容差，避免像素级强约束）

## Sprint 2：Studio Essential Editing（V1 真可用编辑）

### 状态：**DONE（V1）** — 命令链 + 画布/属性面板已接通；体验仍低于 Figma/Canva，但六项可用

### 要做什么
以 Canvas 交互组件为前提，补齐编辑器“最基础可用动作”，并把它们统一落到命令链：

必做（V1 交付标准）：
- 选择：点击选择、悬停高亮联动属性面板；**框选 / Shift 多选**
- 拖拽：单节点与**多节点整体移动**（`MoveNode` / `MoveNodes` → 一次 Revision）
- 缩放：SE 手柄 + Shift 保比例（八向为后续增强）
- 锁定：尊重锁定状态（locked scopes 直接阻断可变字段）
- 删除、图层前后：属性面板删除；画布 **Delete / Backspace** → `DeleteNodeCommand`
- 对齐/分布/**等宽/等高**：多选后属性面板按钮 → `AlignNodesCommand`
- Undo/Redo：沿 `parent_revision_id` 回退；Undo 后新编辑从 **live** 父版本分支；AI/Theme 接受清空 Redo
- 画布直编：双击文本 → `commitText`；双击图片 → 换图（`ReplaceAssetCommand`）
- 图片替换：`ReplaceAssetCommand`（属性面板与画布统一命令链，不再绕 `VisualEdit` intent）
- **文字颜色 / 字号 / 色块填充**：属性面板 → `UpdateNodeStyleCommand`

### Pointer 性能契约（必须）
```text
pointermove → 仅浏览器本地预览（无 Streamlit rerun）
pointerup  → 一次 Command → 一次后端持久化 → 一次 rerun
```

### 验收流程（以真实任务验收为主）
- 导入一个包含主图纸 + 图注 + 照片网格的典型 slide
- 框选图注与主图，左对齐；多选拖动一次应只产生一个 Scene Revision
- 双击标题改字；双击照片换图（不强制绕右侧表单）
- 锁定图纸后替换右侧第二张照片
- Undo 分支：Move→Resize→Undo→新 Move，确认旧 Resize 版本仍在历史且新版本 parent 为 Undo 后的 live
- 撤销两次、再恢复一次；接受 AI/Theme 提案后 Redo 不可用
- 浏览器拖拽约 2s：拖动过程无整页闪烁；松手后才刷新
- 最终导出 PPTX 并确保画面结构不丢失

## Sprint 3：Image Harmonization（图片衍生与安全统一）

### 状态：**PARTIAL+**（Pillow V3 Image Intelligence；非 Sharp / 非生成式修复）

| 能力 | 状态 |
|------|------|
| 管线 `Original → Spec → Derivative → Scene URI` | **已接通**（`StudioSceneService.compile_scene`） |
| Pillow 执行器 | EXIF+sRGB；`SAFE_NORMALIZE` / `PRESENTATION_UNIFY` / `DOCUMENT_SCAN`；落盘 `cache/derivatives/` |
| 可调 unify（色温/饱和度/对比度/亮度） | **已做**（`ImageUnifyParams`；deck 共用默认） |
| 启发式智能裁切（主体/天际线） | **已做**（`ImageFocusDetector`；置信度 &lt;0.35 不裁） |
| 轻度 enhance | **已做**（UnsharpMask / Median denoise / historical_restore 启发式） |
| `ImageProcessor` 门面 | **已做**（非 Agent） |
| Sharp / Node 执行器 | 未接入（**正确**，不在 PptxGen 加滤镜） |
| Soft vignette overlay | **已做**（仅非证据/图纸的 presentation unify） |
| 模型级自动主体检测 | 未做 |
| 生成式老照片修复 | 未做（historical_restore 仅为轻度去噪+对比） |
| 证据策略 clamp | **已做**（证据/图纸不可 `presentation_unify` / overlay） |
| PptxGen 内临时滤镜 | **禁止** |

**不要混淆：**
- `ImageTreatmentPlanningService`：仅 layout fit + `PhotoTreatment` **策略枚举**
- `ImageTreatmentSpecPlanner` + `ImageProcessor` + `ImageDerivativeExecutor`：像素衍生管线
- 页面复活 OCR/VLM：区域理解 / 恢复，**不是**照片视觉统一

### 管线

```text
OriginalAsset
  → ImageTreatmentSpec   (政策：mode / unify / enhance / crop_strategy)
  → ImageProcessor.enrich (启发式 focal；低置信不裁)
  → ImageDerivative      (Pillow：EXIF→sRGB→unify→enhance→crop→vignette→downscale)
  → RenderScene.storage_uri  (derivative；asset_id 仍指向原图)

PptxGen / AssetPathResolver 只消费 URI，不做滤镜。
```

开关：`image_derivatives_enabled`（默认 true）

### 仍待
1. Sharp/Node 或外部模型作为可插拔主体检测
2. Deck 级色统计（从 20 张采样均值再统一）— 当前为 DesignSystem 共用 knobs
3. DB 级 derivative 元数据索引（当前靠文件缓存 + params_hash）
4. 组件级截图 golden 覆盖 unify

### 验收指标
- 证据类策略不破坏事实性表达（QA 规则 + 回归截图）
- 同一 `original_asset_id` 可回溯 derivative 参数与版本（params_hash）
- 混合来源照片观感统一且不过度改色

## Sprint 4：Layout Grammar Expansion（布局族参数化与变体选择）
### 要做什么
在不引入“全自由求解器”的前提下，把现有布局家族升级为 grammar：
- family → variants
- 对每个 variants 建立内容适配规则（标题长度、图注长度、照片数量/比例）
- 提供 fallback：当内容不适配时触发拆页或替换 family
- 仅在复杂页面启用更昂贵的 repair/constraint 逻辑

### 验收指标
- 对典型内容组合（1/2/3/4/5/6 照片、主次图、对比页、数据页）观感不退化
- 新增变体的失败回退路径可解释（rule codes 可在 QA 报告中看到）

## Sprint 5：Full Visual Regression（从组件到 deck 节奏）
### 要做什么
1. 扩展 baseline 覆盖面：
   - component baselines（图标卡、步骤、照片网格）
   - layout baselines（典型 page family）
   - architectural golden slides（多类型混合）
2. 明确容差策略：
   - 核心组件缺失/重排失败：直接失败
   - 小幅像素漂移：警告或允许阈值
   - text box drift / asset bbox drift：以结构指标判定，而不是强行要求像素一致
3. 建立 baseline 更新机制：
   - 允许在“预期性渲染变化”时更新 baseline
   - 更新必须在 PR 中解释原因（theme change、渲染器版本升级、字体 manifest 变化等）

### 验收指标
- CI 中能抓到“数据通过但视觉不好看”的退化案例
- 更新 baseline 的 PR 有清晰的变更说明与截图证据

## Roadmap 与开发建议顺序（汇总版）
1. IconNode + 组件截图基线（Sprint 1）
2. Studio V1 编辑可用性（Sprint 2）
3. ImageDerivative + 安全视觉统一（Sprint 3）
4. LayoutFamily 参数化/变体扩展（Sprint 4）
5. deck-level 回归扩展（Sprint 5）

## 备注：与现有架构的对齐方式
建议把“视觉能力”统一挂到 RenderScene 的原生节点与渲染器组件上，避免把关键规则散落在 UI 或模板层，确保：
- 可编辑性：Studio 使用同一命令协议修改渲染节点
- 可审计性：patch action 记录可追溯变更
- 可回归性：截图回归只需要覆盖“关键节点组合”，而不是每次人工肉眼抽查

