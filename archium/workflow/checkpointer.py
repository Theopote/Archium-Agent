"""LangGraph checkpoint persistence for presentation workflows."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver


def create_workflow_checkpointer(db_path: Path) -> SqliteSaver:
    """Create a SQLite-backed LangGraph checkpointer."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    return SqliteSaver(conn)
