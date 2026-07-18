"""Programmatic Alembic migration runner."""

from __future__ import annotations

from pathlib import Path

from archium.logging import get_logger

logger = get_logger(__name__, operation="database")

_PROJECT_ROOT = Path(__file__).resolve().parents[3]


def run_pending_migrations() -> None:
    """Apply pending Alembic migrations up to head."""
    try:
        from alembic import command
        from alembic.config import Config
    except ImportError:
        logger.warning(
            "Alembic is not installed; skipping database migrations. "
            'Install with: pip install -e ".[full]"'
        )
        return

    config = Config(str(_PROJECT_ROOT / "alembic.ini"))
    logger.info("Running database migrations (alembic upgrade head)")
    command.upgrade(config, "head")
