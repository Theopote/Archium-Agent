# Cross-Platform Validation Notes

Archium targets **Windows (primary)** and **Linux/macOS (CI + developer)**. This document records known platform differences for Real Project Validation.

## Python

| Item | Policy |
|------|--------|
| Supported versions | **3.11** and **3.12** (`requires-python >=3.11`) |
| Type checking | `mypy` uses `python_version = "3.11"` (lowest supported) |
| CI matrix | Ubuntu latest, Python 3.11 + 3.12 |

## Windows — Chinese paths and spaces

Golden Case **L2 `case_e_real_paths`** materializes files under:

```
tmp/<scratch>/中文路径/项目 资料/任务书 摘要.docx
```

Ingestion uses `pathlib.Path` end-to-end; no manual string encoding. If import fails on Windows:

1. Confirm project path does not exceed `MAX_PATH` without long-path support.
2. Prefer UTF-8 code page (`chcp 65001`) in legacy terminals.
3. Avoid mixing short (8.3) paths with Unicode project roots.

## Fonts (PptxGenJS / PowerPoint)

Native-element PPTX uses theme fonts from `archium/infrastructure/renderers/pptxgen/core/theme.mjs`.

| Platform | Behavior |
|----------|----------|
| Windows + Office | Uses installed Chinese fonts (e.g. 微软雅黑) when available |
| Linux CI | Falls back to Latin fonts; **Chinese glyphs may substitute** — file opens, layout intact |
| Validation | Smoke test checks slide count, titles, speaker notes — not pixel-perfect typography |

Opening exported PPTX on Windows with Microsoft PowerPoint is the authoritative visual check (L3 manual).

## Node.js / PptxGenJS

```bash
cd archium/infrastructure/renderers/pptxgen
npm install
node render.mjs --input ../../../tests/fixtures/pptxgen/smoke.spec.json --output /tmp/smoke.pptx
```

CI runs `pytest tests/smoke/test_pptxgen_render.py` after `npm install`.

## SQLite / Checkpointer (Windows)

`WorkflowCheckpointerManager` must be closed before deleting checkpoint DB files. Streamlit uses `@st.cache_resource` lifecycle; tests call `service.close()` explicitly.

## Recommended local validation (Windows)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[full,legacy,dev]"
cd archium/infrastructure/renderers/pptxgen; npm install; cd ../../../../
pytest tests/golden -v
pytest tests/smoke/test_pptxgen_render.py -v
ruff check archium tests
mypy archium
streamlit run app.py
```

Place sanitized real PDFs under `tests/golden/fixtures/files/<case_id>/` to override inline fallbacks.
