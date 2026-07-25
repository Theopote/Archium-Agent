"""LLM planners for Narrative role — propose drafts only.

Architecture boundary (Agents audit):
- ``archium/agents/`` may hold pure LLM *planners* (no Session / no persist).
- Application Services under ``archium/application/narrative/`` own
  context gathering, history, lineage, and repository writes.

``SlidePlanner`` is a compatibility alias of ``SlidePlanService`` (Session-bound
Narrative service). New code should import ``SlidePlanService`` directly.
"""
