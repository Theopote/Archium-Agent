"""Stable in-process Application API — Streamlit and future HTTP share this boundary.

Resource paths (product-facing names, not HTTP yet):

    /project /documents /context /mission /planning /storyline
    /slides /scenes /visual /revisions /render /delivery /jobs

Contract summary (see docs/architecture/current-system.md §APP-029):

- UI must not touch Repositories; Application services still may.
- Durable cross-refresh work goes through JobsApi (progress / cancel /
  idempotency_key / list_active). Sync export and LangGraph WorkflowRun
  are explicit non-job paths — do not claim everything is a BackgroundJob.
- Job idempotency is create-once per (project, idempotency_key), not
  business-artifact uniqueness. Refresh recovery covers durable jobs, not
  ephemeral Streamlit session_state drafts.
"""

from __future__ import annotations

from archium.application.api.context import ContextApi
from archium.application.api.delivery import DeliveryApi
from archium.application.api.documents import DocumentsApi
from archium.application.api.jobs import JobsApi
from archium.application.api.mission import MissionApi
from archium.application.api.planning import PlanningApi
from archium.application.api.project import ProjectApi
from archium.application.api.render import RenderApi
from archium.application.api.revisions import RevisionsApi
from archium.application.api.scenes import ScenesApi
from archium.application.api.session import ApiContext, api_from_session
from archium.application.api.slides import SlidesApi
from archium.application.api.storyline import StorylineApi
from archium.application.api.visual import VisualApi

__all__ = [
    "ApiContext",
    "ContextApi",
    "DeliveryApi",
    "DocumentsApi",
    "JobsApi",
    "MissionApi",
    "PlanningApi",
    "ProjectApi",
    "RenderApi",
    "RevisionsApi",
    "ScenesApi",
    "SlidesApi",
    "StorylineApi",
    "VisualApi",
    "api_from_session",
]
