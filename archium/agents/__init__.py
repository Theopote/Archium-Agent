"""LLM planners for Narrative role — propose drafts only.

Architecture boundary (Agents audit / P0):
- ``archium/agents/`` may hold pure LLM *planners* (no Session / no persist).
- Application Services under ``archium/application/`` own Session, history,
  lineage, citation resolution, and repository writes.
- Prefer ``archium.application._helpers`` over ``archium.agents._helpers``.
- Citation helpers: ``archium.application.citation_resolution``.
- Slide planning: ``archium.application.narrative.SlidePlanService``
  (do not reintroduce Session-bound classes under agents/).
"""
