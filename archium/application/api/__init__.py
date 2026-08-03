"""Stable in-process Application API — Streamlit and future HTTP share this boundary.

Resource modules mirror product paths: /project /documents /context /mission
/storyline /slides /scenes /revisions /render /delivery (+ /jobs).
"""

from __future__ import annotations

from archium.application.api.context import ContextApi
from archium.application.api.delivery import DeliveryApi
from archium.application.api.documents import DocumentsApi
from archium.application.api.jobs import JobsApi
from archium.application.api.mission import MissionApi
from archium.application.api.project import ProjectApi
from archium.application.api.render import RenderApi
from archium.application.api.revisions import RevisionsApi
from archium.application.api.scenes import ScenesApi
from archium.application.api.session import ApiContext, api_from_session
from archium.application.api.slides import SlidesApi
from archium.application.api.storyline import StorylineApi

__all__ = [
    "ApiContext",
    "ContextApi",
    "DeliveryApi",
    "DocumentsApi",
    "JobsApi",
    "MissionApi",
    "ProjectApi",
    "RenderApi",
    "RevisionsApi",
    "ScenesApi",
    "SlidesApi",
    "StorylineApi",
    "api_from_session",
]
