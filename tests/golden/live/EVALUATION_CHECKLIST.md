# Layer 3 — Live Model Evaluation Checklist

手动或定期运行。使用真实 LLM（`ARCHIUM_LIVE_LLM=1`），**不进入默认 CI**。

## A. Mission 规划（M1–M6）— 优先

Mock regression 只证明链路；真实理解必须用 API 跑一轮并人工打分。

### 准备

- [ ] `.env` 已配置 `GEMINI_API_KEY` 或 `LLM_API_KEY`
- [ ] `llm_provider` 非 `mock`

```powershell
$env:ARCHIUM_LIVE_LLM = "1"
# Sprint acceptance: each case at least 3 runs
py scripts/eval_mission_live.py --repeats 3
```

Artifacts:
- Full scorecards → `tests/golden/artifacts/live_mission/<run_id>/`
- Batch index → `tests/golden/live/results/<batch_id>.json`

### 跑完后

- [ ] `tests/golden/artifacts/live_mission/<run_id>/SUMMARY.md` 已生成
- [ ] 六个 case 的 `SCORECARD.md` 已由建筑师/产品填写分数
- [ ] 每个 case 总分 ≥ 70，或记录不合格原因与复跑计划

### 评分表

| 指标 | 分值 | M1 | M2 | M3 | M4 | M5 | M6 |
|------|------|----|----|----|----|----|----|
| 任务性质判断 | 15 | | | | | | |
| 尺度与服务深度 | 10 | | | | | | |
| 事实忠实度 | 20 | | | | | | |
| 关键未知识别 | 15 | | | | | | |
| 澄清问题价值 | 15 | | | | | | |
| Workstream 合理性 | 15 | | | | | | |
| Deliverable 合理性 | 10 | | | | | | |
| **合计** | **100** | | | | | | |

### 特别观察（逐 case 勾选）

| 观察项 | M1 | M2 | M3 | M4 | M5 | M6 |
|--------|----|----|----|----|----|----|
| 编造面积/指标 | | | | | | |
| 专项咨询→完整方案误判 | | | | | | |
| 无价值问题过多 | | | | | | |
| 项目类型当模板 | | | | | | |
| 过度扩大范围 | | | | | | |
| 遗漏关键利益相关方 | | | | | | |

### Case 焦点

| Case | 场景 | 焦点 |
|------|------|------|
| M1 清凉寺 | 重建 | 不编造面积；历史/规模缺口 |
| M2 图书馆 | 改造 | 不停业；分期；汇报+路线图 |
| M3 医院 | 环境提升 | 非新建；患者旅程 |
| M4 村庄 | 更新 | 多主体；反模板 |
| M5 消防站 | 新建 | 保留已给指标 |
| M6 低碳专题 | 专项咨询 | 非完整建筑设计方案 PPT |

---

## B. Presentation 主链（原清单）

### 准备

- [ ] 脱敏真实资料已放入 `tests/golden/fixtures/files/<case_id>/`
- [ ] 可选：Node.js + `npm install`（PptxGenJS）与 Marp CLI 已安装

```bash
set ARCHIUM_LIVE_LLM=1
pytest tests/golden/live -v -m live_llm
```

### 资料导入（真实 parser）

- [ ] PDF 文本层可正确提取（非扫描件或 OCR 后）
- [ ] 扫描件/PDF 图片页有合理 fallback 或明确 warning
- [ ] DOCX / XLSX / PPTX 导入无崩溃
- [ ] 低质量现场照片可导入素材库
- [ ] 中文超长标题/文件名不导致路径错误

### 事实与冲突

- [ ] 多版本面积/容积率冲突被 Fact Ledger 标记
- [ ] 单位混用（㎡ / m2 / 平方米）可被审核或人工发现
- [ ] 重要数字在 SlideSpec 中可追溯到 fact 或 citation

### 生成质量（真实 LLM）

- [ ] Brief 与汇报目的/受众一致
- [ ] Storyline 章节逻辑连贯，无重复段落
- [ ] 20+ 页汇报可完整生成（扩展 `target_slide_count` 试跑）
- [ ] 中文标题无截断乱码
- [ ] 自动修复后复审不保留已解决问题

### 导出与可编辑性

- [ ] JSON / PresentationSpec 结构完整
- [ ] 原生元素 PPTX 可在 PowerPoint 中打开（Win/macOS 各测一次）
- [ ] 文本框可编辑，图片不严重变形
- [ ] Marp PDF / 预览图无明显溢出或裁切
- [ ] PptxGenJS 中文字体在目标机器上可读

### 工作流韧性

- [ ] Brief / Storyline / Slide 审核中断后可 `continue_after_review`
- [ ] 无 Chroma / 无 Marp / 无 Node 时主流程仍可完成 JSON 导出

### 人工修改成本（记录）

| 项目 | 生成页数 | 人工修改时间 | 主要返工点 |
|------|----------|--------------|------------|
| Case A | | | |
| Case B | | | |
| Case C | | | |
| 真实项目 ___ | | | |

**通过标准：** 建筑师愿意在生成结果上继续编辑并用于内部汇报，而非从零重做。
