"""DB-002: cold Alembic upgrade creates schema without prior create_all."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from archium.infrastructure.database.migrations import get_alembic_config
from sqlalchemy import create_engine, inspect, text


def test_cold_alembic_upgrade_creates_core_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "cold.db"
    url = f"sqlite:///{db_path.as_posix()}"
    engine = create_engine(url)
    config = get_alembic_config()
    config.set_main_option("sqlalchemy.url", url)
    config.attributes["engine_url"] = url

    command.upgrade(config, "head")

    tables = set(inspect(engine).get_table_names())
    assert "projects" in tables
    assert "project_facts" in tables
    assert "presentations" in tables
    assert "slides" in tables
    assert "alembic_version" in tables
    with engine.connect() as conn:
        row = conn.execute(text("SELECT version_num FROM alembic_version")).fetchone()
    assert row is not None
    assert row[0]
    # KN-001 column present after 037.
    fact_cols = {c["name"] for c in inspect(engine).get_columns("project_facts")}
    assert "alternate_values" in fact_cols
