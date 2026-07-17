"""Streamlit-scoped workflow resource caching."""

from __future__ import annotations

from pathlib import Path

from archium.config.settings import Settings
from archium.workflow.checkpointer import WorkflowCheckpointerManager


def get_workflow_checkpointer_manager(settings: Settings) -> WorkflowCheckpointerManager:
    """Return a process-wide checkpointer manager, cached in Streamlit when available."""
    db_path = settings.workflow_checkpoint_path
    try:
        import streamlit as st
    except ImportError:
        return WorkflowCheckpointerManager(db_path)

    @st.cache_resource
    def _cached_manager(resolved_path: str) -> WorkflowCheckpointerManager:
        return WorkflowCheckpointerManager(Path(resolved_path))

    return _cached_manager(str(db_path.resolve()))
