"""Tests for file hashing utilities."""

from __future__ import annotations

from pathlib import Path

from archium.infrastructure.storage.local_storage import compute_file_hash


def test_compute_file_hash_is_stable(tmp_path: Path) -> None:
    file_path = tmp_path / "sample.txt"
    file_path.write_text("archium", encoding="utf-8")
    first = compute_file_hash(file_path)
    second = compute_file_hash(file_path)
    assert first == second
    assert len(first) == 64


def test_compute_file_hash_changes_with_content(tmp_path: Path) -> None:
    a = tmp_path / "a.txt"
    b = tmp_path / "b.txt"
    a.write_text("one", encoding="utf-8")
    b.write_text("two", encoding="utf-8")
    assert compute_file_hash(a) != compute_file_hash(b)
