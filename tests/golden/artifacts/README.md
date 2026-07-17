# Golden Case Artifacts

每次运行 `pytest tests/golden` 时，各案例的导出产物会写入对应子目录：

```
artifacts/
├── case_a_hospital/
│   ├── manifest.json
│   └── presentation.json
├── case_b_campus/
│   └── ...
└── case_c_competition/
    ├── manifest.json
    ├── presentation.json
    └── presentation.spec.json
```

PPTX / PDF / 预览图仅在本地安装 Marp / Node.js 且测试启用对应导出选项时才会出现。

CI 会将此目录上传为 workflow artifact，供 v0.2 Alpha Validation Sprint 人工审查。

此目录内容不提交到 git（见根目录 `.gitignore`）。
