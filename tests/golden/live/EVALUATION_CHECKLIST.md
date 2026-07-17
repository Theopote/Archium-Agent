# Layer 3 — Live Model Evaluation Checklist

手动或定期运行。使用真实 LLM（`ARCHIUM_LIVE_LLM=1`），**不进入默认 CI**。

## 准备

- [ ] `.env` 已配置 `GEMINI_API_KEY` 或 `LLM_API_KEY`
- [ ] 脱敏真实资料已放入 `tests/golden/fixtures/files/<case_id>/`
- [ ] 可选：Node.js + `npm install`（PptxGenJS）与 Marp CLI 已安装

```bash
set ARCHIUM_LIVE_LLM=1
pytest tests/golden/live -v -m live_llm
```

## 资料导入（真实 parser）

- [ ] PDF 文本层可正确提取（非扫描件或 OCR 后）
- [ ] 扫描件/PDF 图片页有合理 fallback 或明确 warning
- [ ] DOCX / XLSX / PPTX 导入无崩溃
- [ ] 低质量现场照片可导入素材库
- [ ] 中文超长标题/文件名不导致路径错误

## 事实与冲突

- [ ] 多版本面积/容积率冲突被 Fact Ledger 标记
- [ ] 单位混用（㎡ / m2 / 平方米）可被审核或人工发现
- [ ] 重要数字在 SlideSpec 中可追溯到 fact 或 citation

## 生成质量（真实 LLM）

- [ ] Brief 与汇报目的/受众一致
- [ ] Storyline 章节逻辑连贯，无重复段落
- [ ] 20+ 页汇报可完整生成（扩展 `target_slide_count` 试跑）
- [ ] 中文标题无截断乱码
- [ ] 自动修复后复审不保留已解决问题

## 导出与可编辑性

- [ ] JSON / PresentationSpec 结构完整
- [ ] 原生元素 PPTX 可在 PowerPoint 中打开（Win/macOS 各测一次）
- [ ] 文本框可编辑，图片不严重变形
- [ ] Marp PDF / 预览图无明显溢出或裁切
- [ ] PptxGenJS 中文字体在目标机器上可读

## 工作流韧性

- [ ] Brief / Storyline / Slide 审核中断后可 `continue_after_review`
- [ ] 无 Chroma / 无 Marp / 无 Node 时主流程仍可完成 JSON 导出

## 人工修改成本（记录）

| 项目 | 生成页数 | 人工修改时间 | 主要返工点 |
|------|----------|--------------|------------|
| Case A | | | |
| Case B | | | |
| Case C | | | |
| 真实项目 ___ | | | |

**通过标准：** 建筑师愿意在生成结果上继续编辑并用于内部汇报，而非从零重做。
