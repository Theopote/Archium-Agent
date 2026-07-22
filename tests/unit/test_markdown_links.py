from pathlib import Path

from scripts.check_markdown_links import check, markdown_files, missing_links


def test_markdown_files_discovers_nested_files(tmp_path: Path) -> None:
    nested = tmp_path / "nested"
    nested.mkdir()
    top = tmp_path / "README.md"
    child = nested / "guide.md"
    top.write_text("# Top\n", encoding="utf-8")
    child.write_text("# Guide\n", encoding="utf-8")
    (nested / "ignored.txt").write_text("ignored", encoding="utf-8")

    assert set(markdown_files([tmp_path])) == {top, child}


def test_missing_links_accepts_existing_anchor_and_external_link(tmp_path: Path) -> None:
    guide = tmp_path / "guide.md"
    target = tmp_path / "target.md"
    target.write_text("# Target\n", encoding="utf-8")
    guide.write_text(
        "[target](target.md#section) [web](https://example.com) [mail](mailto:a@example.com)",
        encoding="utf-8",
    )

    assert missing_links(guide) == []


def test_check_reports_missing_relative_target(tmp_path: Path) -> None:
    guide = tmp_path / "guide.md"
    guide.write_text("[missing](missing.md)", encoding="utf-8")

    assert check([tmp_path]) == [(guide, "missing.md")]
