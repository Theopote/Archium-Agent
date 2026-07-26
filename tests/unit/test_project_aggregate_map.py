"""DOM-023 — Project Aggregate Map catalog + identity guards."""

from __future__ import annotations

import ast
import re
from pathlib import Path

from archium.domain.project_aggregate_map import (
    ALLOWED_PROJECT_TABLENAME_PREFIXES,
    ALLOWED_PROJECT_TYPE_NAMES,
    FORBIDDEN_PROJECT_IDENTITY_STEMS,
    PROJECT_AGGREGATE_BRANCHES,
    PROJECT_IDENTITY_TABLENAME,
)

_ROOT = Path(__file__).resolve().parents[2]
_DOMAIN = _ROOT / "archium" / "domain"
_MODELS = _ROOT / "archium" / "infrastructure" / "database" / "models.py"
_ARCH_DOC = _ROOT / "docs" / "architecture" / "current-system.md"


def test_aggregate_branches_documented() -> None:
    assert "cognition" in PROJECT_AGGREGATE_BRANCHES
    assert "delivery" in PROJECT_AGGREGATE_BRANCHES
    assert PROJECT_IDENTITY_TABLENAME == "projects"


def test_architecture_doc_has_project_aggregate_map() -> None:
    text = _ARCH_DOC.read_text(encoding="utf-8")
    assert "Project Aggregate Map" in text
    assert "Project（唯一 identity）" in text or "Project (unique identity)" in text
    assert "LogicalProject" in text
    assert "ProjectProcessBoard" in text


def test_domain_project_type_names_are_allowlisted() -> None:
    found: set[str] = set()
    for path in _DOMAIN.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and "Project" in node.name:
                found.add(node.name)
    unexpected = found - ALLOWED_PROJECT_TYPE_NAMES
    assert not unexpected, f"Unallowlisted *Project* domain types: {sorted(unexpected)}"
    missing_identity = "Project" not in found
    assert not missing_identity


def test_forbidden_project_identity_stems_absent_in_domain() -> None:
    for path in _DOMAIN.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for stem in FORBIDDEN_PROJECT_IDENTITY_STEMS:
            assert f"class {stem}" not in text, f"{path} defines forbidden {stem}"


def test_orm_has_single_project_identity_table() -> None:
    text = _MODELS.read_text(encoding="utf-8")
    tables = re.findall(r'__tablename__\s*=\s*["\']([^"\']+)["\']', text)
    projectish = [name for name in tables if "project" in name.lower()]
    identity = [name for name in projectish if name == PROJECT_IDENTITY_TABLENAME]
    assert identity == [PROJECT_IDENTITY_TABLENAME]
    for name in projectish:
        assert any(
            name == prefix or name.startswith(prefix.rstrip("_") + "_") or name == "projects"
            for prefix in ALLOWED_PROJECT_TABLENAME_PREFIXES
        ), f"Unexpected project-ish table: {name}"
    # Reject parallel identity tables such as logical_projects / workspace_projects
    forbidden_tables = {
        "logical_projects",
        "workspace_projects",
        "research_projects",
        "cad_projects",
        "bim_projects",
        "visual_projects",
    }
    assert not (forbidden_tables & set(tables))
