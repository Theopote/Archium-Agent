# 第二轮-06：AI 绘画系统审计（Vision Engine）

**日期：** 2026-07-26  
**范围：** ConceptVisualPrompt / ResearchVision / VisualIntent.image_request / VisionImageGeneration / illustrative Asset  
**核心问题：** Archium 有没有真正的建筑设计绘画能力，还是「页级插图生成器」？

**前置：** Topic 05 已钉证据 vs 示意分轨（生成图不得进 EVIDENCE）。本专题查**绘画输出侧**，不碰上传理解。

---

## 一句话结论

**Vision Engine 已可用，身份仍偏「页级插图」；设计级视觉种子与页意图分裂。**（P1 后：ConceptVisualPrompt→ImageRequest 带 `seed_source` 可追溯，方向种子优先于 archetype 建议。）

后端（stub / OpenAI / local_sd / ComfyUI）、示意策略、Research→Vision 种子均在。缺口是 deck 一致性与 DesignArtifact（DOM-027），不是再加 Agent。

---

## 理想 vs 现状

```text
理想：
  Direction / VisualConceptBrief（设计视觉身份）
       ↓
  ImageRequest（带 seed_source）→ compile → generate
       ↓
  DesignArtifact（概念图）+ 示意 Asset → 页 hero
       ↓
  册级风格锁

现状：
  ResearchVision / ConceptVisualPrompt ──┐
  VisualConceptBrief ────────────────────┼→ VisualIntent.image_request → Asset(illustrative)
  archetype suggester ───────────────────┘
  （无 DesignArtifact；册级一致性弱）
```

| 能力 | 成熟度 | 落点 |
|------|--------|------|
| 概念草图 / 氛围 / 分析图类型 | B | `ArchitectureImageType` |
| Prompt 编译 + 证据回避 | B+ | `VisionPromptCompiler` |
| 多后端 | B | factory + stub 回退 |
| 示意/证据分轨 | **A-** | Topic 05 + VisionAssetPolicy |
| Direction→页种子桥 | **B（P1）** | `seed_source` + 优先级 |
| 册级风格一致 | C | 每页独立 request |
| DesignArtifact | D | DOM-027 仍开 |

---

## 亮点（勿推倒）

1. 生成默认 `ILLUSTRATIVE_ONLY`；服务层拒绝当证据  
2. ResearchVision 明确「never evidence photos」  
3. Visual 席位服务编排，无第七 Agent  
4. Evidence 页 archetype 不自动绑概念插图  

---

## 建议演进

### Phase P1 — 种子桥（P1）✅ 2026-07-26

1. `ImageRequest.seed_source`：`concept_direction` / `brief` / `suggester` / `research_vision`  
2. 选定方向 `visual_prompt` 优先于 archetype suggester（既有顺序固化 + 可测）  
3. 守卫：方向种子产物经 `ArchitecturalAsset` 仍为 ILLUSTRATIVE  

（关闭 `APP-024`。）

### Phase P2 — 册级一致（P2）

4. 共享 style / DNA 跨非证据页  
5. Visual Thinking 槽位并入同一种子通道  

### Phase P3 — 设计产物身份（延后）

6. 薄 DesignArtifact（DOM-027）；可选设计空间视觉意图 VO  
7. 强一致性 img2img（仍走 VisionImageGenerationService）  

**不做：** 新 Agent；放松证据分轨；平行 VisualProject。

---

## 可行动 Issue

| 编号 | 级别 | 问题 |
|------|------|------|
| APP-024 | P1 | ~~Direction/Brief→ImageRequest 缺 seed_source / 优先级不稳~~ **done (P1)** |
| APP-025 | P2 | 册级 illustrative hero 风格无共享锁 |
| DOM-027 | P1 | （已有）无 DesignArtifact；概念图挂汇报 Asset |
| APP-016 | P2 | Research Critic block（本会话另关） |

---

## 专题衔接

| 专题 | 钩子 |
|------|------|
| 01 Domain | ConceptVisualPrompt vs 页 VisualIntent |
| 05 多模态 | 生成图不得进 EVIDENCE |
| 04 循环 | 弱研究种子会污染绘画（APP-016） |

---

## 验收

- [x] 路径取证与理想对照  
- [x] Issue 草案 APP-024/025  
- [x] Phase P1 落地  
- [ ] P2/P3 排期  
