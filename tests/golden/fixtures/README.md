# Layer 2 — Real Fixture Acceptance

**真实资料 → 真实 parser → 缓存/Mock LLM → 完整导出**

与 Layer 1（inline 文本 + Mock LLM）不同，本层通过 `IngestionService.import_file()` 走真实文档解析路径。

## 添加脱敏资料

将真实文件放入对应子目录（不提交 git，见 `.gitignore`）：

```
files/
└── case_a_hospital/
    ├── 任务书.pdf
    ├── 现场照片说明.docx
    └── 总平面图.jpg
```

Manifest 中 `"required": true` 的文件缺失时，测试会失败；`required: false` 时回退到 manifest 内的 `inline_docx` 段落（用于 CI 无真实文件时仍能验证 DOCX parser）。

## LLM 缓存

可选缓存文件：`llm_cache/<case_id>.json`

```json
{
  "生成 PresentationBrief JSON": "{ ... }",
  "SlidePlan JSON": "{ ... }"
}
```

键为 prompt 子串；未命中时回退到 `pipeline_mock_selector`。

## 运行

```bash
pytest tests/golden/fixtures -v -m fixture_acceptance
```

产物写入 `tests/golden/artifacts/fixture_<case_id>/`。
