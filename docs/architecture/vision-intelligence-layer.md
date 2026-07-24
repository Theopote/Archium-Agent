# Archium Vision Intelligence Layer

> **地位**：战略级能力缺口——把 Archium 从「组织已有资料成汇报」补全为「创造视觉表达以帮助思考、沟通与说服」。  
> **席位**：挂在产品六席的 **Visual** 下（Service / Domain），**不是**第七个 Agent，也不是 Midjourney 套壳。  
> **相关**：[`pipeline-roles.md`](pipeline-roles.md) · [`../visual/architecture.md`](../visual/architecture.md) · Image Harmonization（衍生/统一，≠ 生成）

## 1. 为什么是战略级，而不是锦上添花

建筑表达大量不是最终效果图，而是：

| 目的 | 典型产物 | 人工成本 |
|------|----------|----------|
| 解释概念 | 概念草图 / 意象 | 高 |
| 说明问题 | 分析示意图 / 流线 | 高 |
| 表达关系 | 轴测策略图 / before–after | 高 |
| 营造情绪 | 氛围图 / 封面背景 | 中 |
| 快速沟通想法 | 马克笔草图 / 插图 | 高 |

今天主链大致是：

```text
资料 → 事实 → 叙事 → VisualIntent → Layout → RenderScene → PPTX
```

缺的是 **视觉思维 / 视觉创造** 一环：

```text
资料 → 理解 → 建筑问题 → 设计策略
                ↓
         Vision Engine（概念 / 图示 / 氛围）
                ↓
         Asset（origin=ai_generated）→ Layout / Studio → 汇报
```

没有这一层，Archium 停留在 **AI 建筑汇报助手**；做好之后，才更接近 **AI 建筑表达平台**。

## 2. 非目标（必须先钉死）

| 禁止 | 原因 |
|------|------|
| Midjourney / SD「套壳聊天」 | 无建筑语义，无与 SlideSpec / VisualIntent / QA 闭环 |
| 把生成图默认当「现场照片 / 项目成果」 | 已有门禁 `SEMANTIC.AI_IMAGE_PRESENTED_AS_REAL_PROJECT`；证据槽禁止 `ai_generated`（schema 默认） |
| 新开 `VisionAgent` / `ImageAgent2` | 违反六席硬上限；能力进 Visual services |
| v0.1 自建大规模本地 SD 训练栈 | 先 API 可插拔；本地模型是后续选项 |
| 在 PptxGen 内临时滤镜生成图 | 生成结果先入 Asset / Derivative，再进 Scene |

## 3. 与现有模块的关系

```text
Narrative (SlideSpec)
    ↓
Visual
  ├── ArtDirection / VisualIntent / PageArchetype / Grammar slots
  ├── Vision Engine  ← NEW（创造视觉信息）
  ├── Image Intelligence（统一/裁切/来源分类；处理已有与生成图）
  ├── LayoutPlan / RenderScene
  └── Studio（人选、换图、锁定、Undo）
    ↓
Render → PPTX
    ↓
Critic（含 AI 图冒充现场证据）
```

已存在、可复用的挂钩：

| 已有 | 用途 |
|------|------|
| `ModelRole.IMAGE_GENERATION` / `IMAGE_EDITING` | 模型路由（`model_roles.py`） |
| `asset_origin="ai_generated"` | RenderScene / ReplaceAsset |
| Schema `forbidden_asset_origins` 含 `ai_generated` | 证据页默认禁止 |
| `SEMANTIC.AI_IMAGE_PRESENTED_AS_REAL_PROJECT` | 导出门禁 |
| ImageDerivative / StyleMatcher | 生成后安全统一（可选） |
| Studio `ReplaceAssetCommand` | 人工接受后换上生成图 |

## 4. Vision Engine 架构

```text
Architectural context
  (project type, phase, audience, page archetype, evidence policy)
        ↓
 Prompt Compiler          ← 核心壁垒（不是裸 prompt）
        ↓
 Image Generator adapter  (OpenAI / Flux / SD API / …)
        ↓
 Image Evaluator (QA)     (风格、可读性、禁用项、是否像「假现场照」)
        ↓
 Asset Library            (origin=ai_generated, provenance, prompt hash)
        ↓
 VisualIntent / Layout / Studio / Render
```

建议包结构（实现时再落地，勿提前堆空壳）：

```text
archium/
  domain/visual/vision_*.py          # ImageType, ImageRequest, GenerationSpec
  application/visual/vision/
    prompt_compiler.py
    image_generation_service.py
    image_evaluator.py
    style_preset_registry.py
  infrastructure/vision_gen/         # provider adapters（可插拔）
```

**不**新增 Pipeline 产品席位；内部可标 `PipelineRole.VISUAL`。

## 5. 六类能力（产品分类）

| # | 类型 | 用途 | v0.1 | v0.2 | v0.3 |
|---|------|------|------|------|------|
| 1 | **Concept** | 早期意象 / 概念草图 | ○ | ● 模板默认 | ● |
| 2 | **Architectural Diagram** | 流线、策略、庭院切开、before–after 示意 | ○ 文生图示意 | ● 底图+Pillow 叠加 | ● 图纸条件改图 |
| 3 | **Style Transfer / Edit** | 老照片→改造意象、材料/夜景变体 | – | – | ● 照片条件改图 |
| 4 | **Atmosphere / Background** | 封面与氛围底图 | ● | ● | ● |
| 5 | **Sketch** | 手绘/马克笔/铅笔感（非商业摄影） | ● 风格预设 | ● 风格包注册表 | ● |
| 6 | **Presentation Illustration** | 页级抽象插图，服务 PPT | ● | ● | ● |

「○」= 启发式可用；「●」= 正式能力；「–」= 不做。

## 6. Prompt Compiler（壁垒）

用户说：「表现医院增加风雨连廊的概念」。

Compiler 应注入：

- 项目类型 / 阶段（概念 vs 报批）
- 页目的（说明问题 vs 展示成果）
- 受众（政府汇报 / 内部讨论）
- 视觉语法（竞赛概念草图 vs 商业效果图）
- **Avoid 列表**（豪华商业渲染、伪现场照、无依据的科幻形体）
- 与 `PageArchetype` / `VisualIntent` / Design Brief 对齐的主体与元素

输出：结构化 `GenerationSpec`（subject、purpose、style、elements、avoid、aspect、negative），再编译为各 provider 的 prompt——**用户永远不必手写 Midjourney 咒语**。

## 7. 与 SlideSpec / VisualIntent 的契约（目标形态）

今日（文字主导）：

```json
{
  "title": "交通优化策略",
  "message": "增加风雨连廊"
}
```

目标（意图可生成图）：

```json
{
  "title": "交通优化策略",
  "message": "增加风雨连廊",
  "visual_intent": {
    "dominant_content_type": "diagram",
    "image_request": {
      "image_type": "architectural_diagram",
      "subject": "covered walkway on existing hospital campus",
      "style": "axonometric_diagram_sketch",
      "purpose": "explain_weather_protected_circulation",
      "asset_policy": "illustrative_only"
    }
  }
}
```

规则：

- `asset_policy=illustrative_only` → 可自动建议插入非证据槽
- 证据槽 / `SITE_PHOTO` / grammar evidence → **不得**静默用生成图填；需用户明确「仅示意」并打标
- 接受进稿：走 Asset 入库 +（可选）Studio 确认 / Proposal，不绕过命令链

## 8. 分阶段交付

### Vision Engine v0.1 — **DONE**

| 项 | 状态 |
|----|------|
| Domain：`ArchitectureImageType` / `ImageRequest` / `GenerationSpec` | **已做**（`domain/visual/vision_generation.py`） |
| `VisualIntent.image_request` | **已做** |
| `VisionPromptCompiler` | **已做**（规则编译 + avoid/证据诚信） |
| 可插拔 Generator | **Stub**（Pillow 示意图，离线可测） |
| 落盘 `assets/vision_generated/` + metadata provenance | **已做**（可选 DB Asset） |
| OpenAI / Flux 等真实 API adapter | **已做** `openai_compatible`（默认关闭；未配置回退 stub） |
| Studio「为当前页生成示意」按钮 | **已做**（属性面板 Vision 示意生成 → 入库 / 可选换图） |
| 自动插入证据槽 | **禁止**（仍靠 schema / Critic） |

启用外部 API（示例 env）：

```text
VISION_IMAGE_GENERATION_ENABLED=true
VISION_IMAGE_GENERATION_PROVIDER=openai_compatible
VISION_IMAGE_GENERATION_MODEL=dall-e-3
# 可选；缺省回退 LLM_API_KEY
VISION_IMAGE_GENERATION_API_KEY=...
VISION_IMAGE_GENERATION_BASE_URL=https://api.openai.com/v1
```

路径：

```text
ImageRequest (+ VisionGenerationContext)
  → VisionPromptCompiler
  → VisionImageGenerator (stub | openai_compatible)
  → assets/vision_generated/* + optional Asset(origin=ai_generated)
  → Studio ReplaceAsset（人工选择目标图）
```

服务入口：`archium.application.visual.vision.VisionImageGenerationService`  
Studio 入口：`generate_slide_vision_illustration` / 属性面板「Vision 示意生成」

**验收（当前）**：风雨连廊类请求可编译 prompt；stub 或 API 产出 PNG；Studio 可入库并可选应用到图片元素；证据语义仍拒绝静默冒充。

### Vision Engine v0.2 — **PARTIAL（模板 + 底图叠加已落地）**

| 项 | 状态 |
|----|------|
| 类型模板固化（8 类 + 中文标签 / 默认风格 / 默认元素） | **已做** `style_preset_registry.py` |
| 风格包：手绘 / 马克笔 / 竞赛 / 轴测 / 扁平分析 / 氛围 / 水彩 | **已做** |
| `ImageRequest.style=None` → 按图类默认 | **已做** |
| Diagram 轻量合成：用户总平底图 + 策略箭头/标注层 | **已做** `diagram_composer.py`（Pillow；非 CAD） |
| Studio：图类扩展 + 底图选择 + 叠加标注 | **已做** |
| 条件生成 / 图生图 API | **已做（v0.3）** |

Compose 路径（场地/流线 + 可解析底图时优先）：

```text
base site/plan image
  → desaturate + fit
  → overlay arrows / zones / cue chips
  → Asset(origin=ai_generated, illustrative, provider=diagram_composer)
```

无底图时仍走 stub / openai_compatible 文生图。

### Vision Engine v0.3 — **PARTIAL（条件改图 + QA + 软统一）**

| 项 | 状态 |
|----|------|
| `VisionGenerationMode`：文生图 / 照片改图 / 图纸改图 | **已做** |
| 底图 Photo QA（sharpness / exposure，软门禁） | **已做** `image_evaluator.py` |
| 本地条件改图（Pillow，示意改造意象） | **已做** `conditioned_editor.py` |
| OpenAI-compatible `images.edit`（失败回退本地） | **已做** |
| 生成后软统一（Derivative 精神：色度/对比微调） | **已做** `soft_harmonize_png` |
| Studio 模式切换 + 底图 QA 警告 | **已做** |
| 完整图生图本地 SD / 主体检测 | **未做**（后续） |

Edit 路径：

```text
base photo/drawing
  → VisionImageEvaluator (warn blur/overexpose; block tiny)
  → VisionPromptCompiler (edit semantics + evidence avoid)
  → provider.edit OR conditioned_editor
  → soft_harmonize_png (optional)
  → Asset(origin=ai_generated, illustrative)
```

## 9. 质量与诚信

| 检查 | 行为 |
|------|------|
| 生成图进证据槽 | 默认拒绝；UI 明示「示意」 |
| 导出 | `AI_IMAGE_PRESENTED_AS_REAL_PROJECT` 可阻断 |
| 水印 / 元数据 | Asset.metadata 保留 model、prompt_hash、`illustrative` |
| 图文一致 | Critic / Semantic：标题谈「现状照片」却绑 `ai_generated` → 告警 |

## 10. 路线图位置（相对当前冲刺）

当前 Visual Quality sprint 的非目标写明「不做完整 LLM 自动效果图生成」——**仍适用于该冲刺收口**。  
Vision Engine 作为 **下一条战略主线** 立项，不阻塞 Studio V1 / Image Harmonization / Grammar 收尾。

建议优先级：

1. 收口 Studio + 图片统一 + Grammar（进行中）
2. Vision Engine v0.1 — **已完成**
3. Vision Engine v0.2 建筑图类模板 + 底图叠加 — **已完成**
4. Vision Engine v0.3 条件改图 + QA/软统一 — **本轮部分完成**
5. 后续：本地模型 / 更强图生图 / 与 Scene Derivative 全量复用

## 11. 一句话决策

> Archium 需要的不是「会画画的聊天机器人」，而是 **懂建筑语义与汇报诚信的 Vision Engine**：  
> 语义 → Prompt Compiler → 可插拔生成 → QA → Asset → Intent/Layout/Studio/Render。

*Created: 2026-07-24*
