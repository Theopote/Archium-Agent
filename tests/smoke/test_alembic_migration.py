"""Alembic migration smoke tests — upgrade on initialized DB and incremental head."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import archium.infrastructure.database.models  # noqa: F401
import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from archium.config.settings import Settings, reset_settings
from archium.infrastructure.database.base import Base
from archium.infrastructure.database.session import create_engine_from_settings
from sqlalchemy import inspect, text

pytestmark = [pytest.mark.smoke, pytest.mark.migration_smoke]

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_HEAD_REVISION = "040_artifact_jobs"
_PRE_RULE_CODE_REVISION = "004_review_layer"
_BASELINE_REVISION = "003_fact_conflict_group"


def _run_alembic(*args: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["alembic", *args],
        cwd=_PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _migration_env(database_path: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["DATABASE_PATH"] = str(database_path)
    return env


def _initialize_database(database_path: Path) -> None:
    settings = Settings(_env_file=None, database_path=database_path)
    engine = create_engine_from_settings(settings)
    try:
        Base.metadata.create_all(engine)
    finally:
        engine.dispose()


def _expected_orm_tables() -> set[str]:
    return set(Base.metadata.tables.keys())


def _database_tables(database_path: Path) -> set[str]:
    reset_settings()
    settings = Settings(_env_file=None, database_path=database_path)
    engine = create_engine_from_settings(settings)
    try:
        inspector = inspect(engine)
        return set(inspector.get_table_names()) - {"alembic_version"}
    finally:
        engine.dispose()


def _review_issue_columns(database_path: Path) -> set[str]:
    reset_settings()
    settings = Settings(_env_file=None, database_path=database_path)
    engine = create_engine_from_settings(settings)
    try:
        inspector = inspect(engine)
        return {column["name"] for column in inspector.get_columns("review_issues")}
    finally:
        engine.dispose()


def _drop_review_issue_migration_columns(database_path: Path) -> None:
    """Simulate a pre-migration review_issues table missing newer columns."""
    reset_settings()
    settings = Settings(_env_file=None, database_path=database_path)
    engine = create_engine_from_settings(settings)
    try:
        inspector = inspect(engine)
        columns = {column["name"] for column in inspector.get_columns("review_issues")}
        indexes = {index["name"] for index in inspector.get_indexes("review_issues")}
        with engine.begin() as connection:
            if "ix_review_issues_presentation_rule_code" in indexes:
                connection.execute(text("DROP INDEX ix_review_issues_presentation_rule_code"))
            if "ix_review_issues_rule_code" in indexes:
                connection.execute(text("DROP INDEX ix_review_issues_rule_code"))
            if "rule_code" in columns:
                connection.execute(text("ALTER TABLE review_issues DROP COLUMN rule_code"))
            if "reviewer_layer" in columns:
                connection.execute(text("ALTER TABLE review_issues DROP COLUMN reviewer_layer"))
    finally:
        engine.dispose()


def _review_issue_indexes(database_path: Path) -> set[str]:
    reset_settings()
    settings = Settings(_env_file=None, database_path=database_path)
    engine = create_engine_from_settings(settings)
    try:
        inspector = inspect(engine)
        return {index["name"] for index in inspector.get_indexes("review_issues")}
    finally:
        engine.dispose()


def test_alembic_upgrade_head_on_initialized_database(tmp_path: Path) -> None:
    """init_database()/create_all() baseline followed by alembic upgrade head."""
    database_path = tmp_path / "archium-migration-smoke.db"
    _initialize_database(database_path)
    env = _migration_env(database_path)

    upgrade = _run_alembic("upgrade", "head", env=env)
    assert upgrade.returncode == 0, upgrade.stderr or upgrade.stdout

    current = _run_alembic("current", env=env)
    assert current.returncode == 0, current.stderr or current.stdout
    assert _HEAD_REVISION in current.stdout

    assert _expected_orm_tables() == _database_tables(database_path)
    indexes = _review_issue_indexes(database_path)
    assert "ix_review_issues_rule_code" in indexes
    assert "ix_review_issues_presentation_rule_code" in indexes


def test_alembic_incremental_upgrade_from_previous_revision(tmp_path: Path) -> None:
    """Stamp an older revision, then upgrade through review layer + rule_code migrations."""
    database_path = tmp_path / "archium-incremental-migration.db"
    _initialize_database(database_path)
    _drop_review_issue_migration_columns(database_path)
    env = _migration_env(database_path)

    stamp = _run_alembic("stamp", _BASELINE_REVISION, env=env)
    assert stamp.returncode == 0, stamp.stderr or stamp.stdout

    to_review_layer = _run_alembic("upgrade", _PRE_RULE_CODE_REVISION, env=env)
    assert to_review_layer.returncode == 0, to_review_layer.stderr or to_review_layer.stdout
    columns = _review_issue_columns(database_path)
    assert "reviewer_layer" in columns
    assert "rule_code" not in columns

    to_head = _run_alembic("upgrade", "head", env=env)
    assert to_head.returncode == 0, to_head.stderr or to_head.stdout
    columns = _review_issue_columns(database_path)
    assert "rule_code" in columns

    current = _run_alembic("current", env=env)
    assert current.returncode == 0, current.stderr or current.stdout
    assert _HEAD_REVISION in current.stdout


def test_alembic_head_matches_script_directory() -> None:
    config = Config(str(_PROJECT_ROOT / "alembic.ini"))
    script = ScriptDirectory.from_config(config)
    assert script.get_current_head() == _HEAD_REVISION
