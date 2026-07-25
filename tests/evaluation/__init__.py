"""Role-level evaluation — product contracts for cognitive cores / pipeline seats.

These tests assert **output shapes and obligations** (non-empty strategy fields,
citations, critic counterexamples). They use Mock LLM only (CI-safe).

Not ``tests/agents/``: Archium forbids proliferating Agent classes; evaluation
targets Services + Domain artifacts under the six seats.

Run::

    pytest tests/evaluation -q
"""
