"""Structured logging setup for Archium."""

from __future__ import annotations

import logging
import sys
from collections.abc import MutableMapping
from typing import Any

from archium.config.settings import Settings

DEFAULT_FORMAT = (
    "%(asctime)s | %(levelname)-8s | %(name)s | "
    "project=%(project_id)s | presentation=%(presentation_id)s | "
    "workflow=%(workflow_run_id)s | %(operation)s | "
    "%(message)s"
)


class ArchiumLogAdapter(logging.LoggerAdapter):
    """Logger adapter that injects Archium context fields."""

    def process(
        self,
        msg: str,
        kwargs: MutableMapping[str, Any],
    ) -> tuple[str, MutableMapping[str, Any]]:
        extra = kwargs.setdefault("extra", {})
        for key in ("project_id", "presentation_id", "workflow_run_id", "operation"):
            extra.setdefault(key, "-")
        return msg, kwargs


def setup_logging(settings: Settings | None = None, *, debug: bool | None = None) -> None:
    """Configure root logging for the application."""
    if settings is None:
        from archium.config.settings import get_settings

        settings = get_settings()

    level_name = settings.log_level.upper()
    if debug is True:
        level_name = "DEBUG"
    level = getattr(logging, level_name, logging.INFO)

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(DEFAULT_FORMAT))
    root.addHandler(handler)

    logging.getLogger("archium").setLevel(level)


def get_logger(
    name: str,
    *,
    project_id: str = "-",
    presentation_id: str = "-",
    workflow_run_id: str = "-",
    operation: str = "-",
) -> ArchiumLogAdapter:
    """Return a logger with optional Archium context."""
    base = logging.getLogger(name)
    return ArchiumLogAdapter(
        base,
        {
            "project_id": project_id,
            "presentation_id": presentation_id,
            "workflow_run_id": workflow_run_id,
            "operation": operation,
        },
    )
