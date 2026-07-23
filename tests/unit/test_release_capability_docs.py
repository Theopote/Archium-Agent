"""Guards for release capability matrix + user-task playbooks."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parents[2]
_MATRIX = _ROOT / "docs" / "release-capability-matrix.md"
_PLAYBOOKS = _ROOT / "docs" / "user-task-playbooks.md"
_README = _ROOT / "README.md"

_RELEASE_LEVELS = {
    "Prototype",
    "Experimental",
    "Preview",
    "Beta",
    "Stable",
    "Deprecated",
}

_PLAYBOOK_IDS = ("A", "B", "C", "D", "E")


def test_release_levels_are_documented() -> None:
    text = _MATRIX.read_text(encoding="utf-8")
    for level in _RELEASE_LEVELS:
        assert f"**{level}**" in text, f"missing release level {level}"


def test_capability_matrix_uses_four_evidence_columns() -> None:
    text = _MATRIX.read_text(encoding="utf-8")
    header = next(line for line in text.splitlines() if line.startswith("| 能力 |"))
    assert "代码" in header
    assert "自动测试" in header
    assert "真实项目验收" in header
    assert "发布等级" in header
    assert "可稳定使用" not in header
    assert "已接主流程" not in header


def test_matrix_rows_use_known_release_levels() -> None:
    text = _MATRIX.read_text(encoding="utf-8")
    # Rows look like: | name | ✅ | ✅ | ⚠️ | Preview |
    row_re = re.compile(
        r"^\| (?!能力)(?![-:| ]+$).+\| .+\| .+\| .+\| (?P<level>[^|]+)\|$",
        re.M,
    )
    levels_found: set[str] = set()
    for match in row_re.finditer(text):
        raw = match.group("level").strip()
        # Allow "Preview / Experimental" dual tags.
        parts = [part.strip() for part in re.split(r"[/,]", raw) if part.strip()]
        for part in parts:
            # Strip markdown bold if any
            part = part.replace("*", "")
            if part in {"-----", ":--------:"}:
                continue
            levels_found.add(part)
            assert part in _RELEASE_LEVELS, f"unknown release level {part!r} in matrix"
    assert levels_found & {"Experimental", "Preview", "Deprecated"}


def test_five_user_task_playbooks_exist() -> None:
    text = _PLAYBOOKS.read_text(encoding="utf-8")
    for playbook_id in _PLAYBOOK_IDS:
        assert re.search(rf"^## 剧本 {playbook_id}\b", text, re.M), playbook_id
    assert "每次发版检查表" in text
    assert "v0.2-beta" in text


def test_playbook_a_documents_repeatable_gate_script() -> None:
    text = _PLAYBOOKS.read_text(encoding="utf-8")
    section = text.split("## 剧本 A", 1)[1].split("## 剧本 B", 1)[0]
    assert "scripts/run_playbook_a_gate.py" in section
    script = _ROOT / "scripts" / "run_playbook_a_gate.py"
    assert script.is_file()
    body = script.read_text(encoding="utf-8")
    assert "tests/golden/regression" in body
    assert "tests/golden/mission" in body
    assert "tests/smoke/test_pptxgen_render.py" in body


def test_readme_points_to_matrix_and_playbooks() -> None:
    text = _README.read_text(encoding="utf-8")
    assert "docs/release-capability-matrix.md" in text
    assert "docs/user-task-playbooks.md" in text
    section = text.split("## 能力与发布等级", 1)[1].split("## 应用入口", 1)[0]
    assert "| 能力 | 代码 | 自动测试 | 真实项目验收 | 发布等级 |" in section
    assert "| 功能 | 已实现 | 有测试 | 已接主流程 | 可稳定使用 |" not in section
