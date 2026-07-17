# Golden Case Regression Suite

Part of the **[v0.2 Alpha Validation Sprint](../../docs/v0.2-alpha-validation-sprint.md)**.

Each case ships fixed source material and deterministic mock-LLM expectations. Tests assert workflow outcomes and save export artifacts under `artifacts/` for manual review.

## Case A — 医院老院区更新 (`case_a_hospital`)

Validates:

- Multi-source fact conflicts (`site_area` / `land_area` semantic alias)
- Traffic / circulation narrative for healthcare campus
- Site photo and plan evidence hooks
- Client decision-oriented briefing

## Case B — 校园建筑改造 (`case_b_campus`)

Validates:

- Existing-condition problem framing
- Phased implementation storyline
- Functional reallocation slides
- Before/after comparison layouts
- Area metrics on data slides

## Case C — 概念方案投标 (`case_c_competition`)

Validates:

- Fast document import path
- Narrative-first storyline
- Full-bleed hero image layouts
- Highlight thesis slides
- Native-element PPTX export path (PresentationSpec)

## Running

```bash
pytest tests/golden -v
```

Artifacts are written to `tests/golden/artifacts/<case_id>/` (manifest + JSON/Spec; PPTX/PDF/previews when Marp/Node available).

Do not start new feature Stages until the Validation Sprint checklist is complete and CI stays green.
