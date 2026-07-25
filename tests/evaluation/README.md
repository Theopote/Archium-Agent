# Role-level evaluation (product contracts)

Deterministic **Mock LLM** checks for cognitive-core / seat output obligations.
Complements `tests/golden/` (workflow regression) and `tests/unit/` (implementation).

| File | Seat / core | Contract |
|------|-------------|----------|
| `test_concept_direction_eval.py` | Architectural Reasoning | 山地文化中心 → spatial_strategy / formal_language / risks；DesignIntent.social_background |
| `test_autonomous_research_eval.py` | Research | citations + DesignKnowledge + ResearchCritique scores |
| `test_design_critique_eval.py` | Critic | alternative_directions (counterexamples) |
| `test_presentation_quality_eval.py` | Presentation Delivery | PresentationIntent + Storyline chapters + SlideRole + PresentationCritic |

```bash
pytest tests/evaluation -q
```

Do **not** put live-API quality scoring here (see `tests/golden/live/`).
