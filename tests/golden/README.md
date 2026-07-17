# Golden Case Regression Suite

Stage 17 development is **paused** until these three fixed acceptance projects pass reliably.

Each case ships fixed source material and deterministic mock-LLM expectations. Tests assert workflow outcomes — not ad-hoc feature counts.

## Case A — 医院老院区更新 (`case_a_hospital`)

Validates:

- Multi-source fact conflicts
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

Add new Stages only after all golden cases stay green on CI.
