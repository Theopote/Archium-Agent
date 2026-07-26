# 第二轮-05：多模态建筑输入审计

**日期：** 2026-07-26  
**范围：** 上传 / 解析 / Asset / Vision caption / MultimodalRetrieval / OCR / ProjectContext 证据通道  
**核心问题：** Archium 能否把现场照片、图纸、扫描 PDF 读进建筑设计世界模型，还是只能做成「可检索的图注 + 汇报绑图」？

**前置：** Topic 01–04 已钉世界模型骨架、知识槽、推理链与设计循环。本专题查**输入侧多模态**是否接上认知面，不碰 Topic 06 绘画生成。

---

## 一句话结论

**能入库与 caption RAG；M1–M3 已接通证据、弱种子与 IFC 文本→事实。几何/CLIP/平面拓扑仍欠。**

`ArchitecturalAsset` + EVIDENCE + typed sources + OCR + 弱 IdeaSeed + CAD UI + IFC 计数/Name→`ProjectFact` 已落地。完整 CAD 几何、平面拓扑 CV、默认 CLIP 仍不做。生成图禁作现场证据。

---

## 理想 vs 现状

```text
理想：
  现场照片 / 草图 / 平面 PDF / CAD
       ↓
  ArchitecturalAsset（统一读入口）
       ↓
  证据事实 / 约束 / IdeaSeed / Direction 种子
       ↓
  Design Critic 闸门（Topic 04）

现状（审计时）：
  Upload → Ingestion → SourceDocument + Asset + Chunk
              ↓
       AssetVisionRag（caption；LLM 默认关）
              ↓
       MultimodalRetrieval → KnowledgeReference（偏 ILLUSTRATIVE）
              ↓
       ProjectContext：documents:N   ✗ 无 site_photo:N
       Presentation：SlideAssetBinding ✓
```

| 理想能力 | 成熟度 | 落点 |
|----------|--------|------|
| 文件入库 | A- | UI upload + `IngestionService` |
| Vision caption → RAG | B | `AssetVisionRagService`；LLM 可选 |
| 汇报绑图 | B+ | `SlideAssetBinding` / VisualIntent |
| 项目素材作设计证据 | **B-（M1）** | `ArchitecturalAsset` + EVIDENCE usage + typed sources |
| 扫描 PDF OCR | **B-（M1 切片）** | `NEEDS_OCR` → `ocr_text` chunks |
| 现场图 → 约束 | C+ | 弱种子（M2）；IFC→facts（M3）；照片自动约束仍弱 |
| 草图 → IdeaSeed | **B（M2）** | `visual_idea_seed`；enrich=False；不自动选定 |
| CAD/BIM 几何 | D | UI 可上传；**IFC 文本语义→事实（M3）**；无几何 |
| CLIP 图像检索 | D | Protocol 预留未接 |

---

## 取证摘要

| 层 | 事实 |
|----|------|
| 入口 | Workspace / Studio 上传 `pdf,docx,pptx,xlsx,png,jpg,…`；**无** CAD UI 类型 |
| 域 | `SourceDocument` / `Asset` / `DocumentChunk`；无聚合门面（→ DOM-031） |
| 服务 | Ingest → vision caption → Fusion；`ResearchVision` 明确 illustrative-only |
| Context | `input_sources` 仅 documents/facts/knowledge（→ APP-018） |
| OCR | 标 `NEEDS_OCR` 但不跑；slide recovery 另有 pytesseract（→ KN-005） |

---

## 亮点（勿推倒）

1. 生成图 / ResearchVision **禁止当现场证据**  
2. `KnowledgeUsage.EVIDENCE` 枚举已在，只是检索未用  
3. Asset 与 Document 分表正确；勿合成第二套 Project（DOM-023）  
4. Caption RAG 让视觉可参与 Research prompt，不必等 CLIP  

---

## 建议演进

### Phase M1 — 证据通道（P0/P1）✅ 2026-07-26

1. 薄 `ArchitecturalAsset` 读模型门面（无新表）  
2. 项目素材 photo/drawing → `KnowledgeUsage.EVIDENCE`；参考/生成保持 ILLUSTRATIVE  
3. `ProjectContext.input_sources` 增加 `site_photo:N` / `drawing:N` 等  
4. `NEEDS_OCR` 可测 OCR → `ocr_text` chunks；成功则 COMPLETED  

（关闭 `DOM-031` / `APP-017` / `APP-018`；推进 `KN-005`。）

### Phase M2 — 设计种子（P2）✅ 2026-07-26

5. 现场图/图纸 → 弱 `IdeaSeed`（`enrich=False`；不自动推演/选定）；开放探索可合并附录  
6. UI 上传暴露 CAD/BIM 后缀（`dwg/dxf/ifc/rvt/rfa`）；推演方向时可注入视觉证据 prompt 块  

（关闭 `APP-019` / `APP-020`。）

### Phase M3 — BIM 文本入世界模型（P2）✅ 2026-07-26

7. IFC Name/计数 → `ProjectFact`（floors / constraints / main_function）  
8. `DOCUMENT_ANALYZE` 回写文档 metadata + 事实；证据包含 `cad_bim:N`  
9. 检索对已有 IFC 文本语义改为「文本就绪」提示（仍无几何/CLIP）  

（关闭 `APP-021` / `APP-022` / `APP-023`。）

**仍不做：** DWG 几何、平面拓扑 CV、默认 CLIP、`DesignArtifact`。

**不做：** 新 Agent；平行 Project；把绘画生成并进本专题。

---

## 可行动 Issue

| 编号 | 级别 | 问题 |
|------|------|------|
| DOM-031 | P1 | ~~缺 ArchitecturalAsset 门面~~ **done (M1)** |
| APP-017 | P1 | ~~多模态默认 ILLUSTRATIVE~~ **done (M1)** |
| APP-018 | P1 | ~~input_sources 无视觉类型~~ **done (M1)** |
| KN-005 | P1 | 重解析/`needs_ocr`——**M1 已可测 OCR 切片**；幂等文档继续跟 |
| APP-019 | P2 | ~~草图/现场图未种子化~~ **done (M2)** |
| APP-020 | P2 | ~~UI 未暴露 CAD/BIM~~ **done (M2)** |
| APP-021 | P2 | ~~IFC/CAD 文本未进 ProjectFact~~ **done (M3)** |
| APP-022 | P2 | ~~DOCUMENT_ANALYZE 不回写~~ **done (M3)** |
| APP-023 | P2 | ~~证据包缺 cad_bim~~ **done (M3)** |
| TS-005 | P1 | 整包仍开；多模态 settings（vision/OCR）已绑定使用 |

（写入 `02-domain.md` / `03-application.md` / `06-parsing-knowledge.md`。）

---

## 专题衔接

| 专题 | 钩子 |
|------|------|
| 01 Domain | ArchitecturalAsset 门面落地；仍无 DesignArtifact |
| 02 Knowledge | Asset→图节点仍待；EVIDENCE 用法已可喂 Fusion |
| 04 设计循环 | 输入变宽后 Critique 闸门更关键 |
| 06 绘画 | 输出侧生成；不得污染本专题证据通道 |
| 07 产品闭环 | 上传→认知→设计 旅程完整性 |

---

## 验收（本专题）

- [x] 入口 / 域 / 服务 / Context 取证  
- [x] 理想能力对照与 Issue 草案  
- [x] Phase M1：门面 + EVIDENCE + typed sources + OCR 切片  
- [x] Phase M2：弱 IdeaSeed + CAD UI  
- [x] Phase M3：IFC 文本→事实 + 回写 + cad_bim 证据  
- [ ] 几何/CLIP/平面拓扑（明确延后）
