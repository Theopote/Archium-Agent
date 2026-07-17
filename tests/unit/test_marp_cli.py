"""Unit tests for Marp CLI runner."""

from __future__ import annotations

from pathlib import Path

import pytest
from archium.exceptions import RenderingError
from archium.infrastructure.renderers.marp_cli import MarpCliRunner


def test_marp_cli_convert_requires_installed_binary(
    test_settings: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("archium.infrastructure.renderers.marp_cli.shutil.which", lambda _: None)
    runner = MarpCliRunner(test_settings)  # type: ignore[arg-type]
    markdown_path = tmp_path / "slides.md"
    markdown_path.write_text("---\nmarp: true\n---\n\n# Title", encoding="utf-8")

    with pytest.raises(RenderingError, match="Marp CLI"):
        runner.convert(markdown_path, tmp_path / "output.pptx")


def test_marp_cli_export_images_invokes_subprocess(
    test_settings: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    markdown_path = tmp_path / "presentation.md"
    markdown_path.write_text("---\nmarp: true\n---\n\n# Title", encoding="utf-8")
    previews_dir = tmp_path / "previews"
    calls: list[list[str]] = []

    monkeypatch.setattr("archium.infrastructure.renderers.marp_cli.shutil.which", lambda _: "marp")

    def fake_run(cmd: list[str], **kwargs: object) -> object:
        calls.append(cmd)
        previews_dir.mkdir(parents=True, exist_ok=True)
        (previews_dir / "presentation.001.png").write_bytes(b"png")
        (previews_dir / "presentation.002.png").write_bytes(b"png")
        return type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    monkeypatch.setattr("archium.infrastructure.renderers.marp_cli.subprocess.run", fake_run)

    runner = MarpCliRunner(test_settings)  # type: ignore[arg-type]
    images = runner.export_images(markdown_path, output_dir=previews_dir)

    assert len(images) == 2
    assert images[0].name == "presentation.001.png"
    assert images[1].name == "presentation.002.png"
    assert calls == [
        [
            "marp",
            str(markdown_path),
            "--images=png",
            "-o",
            str(previews_dir) + "/",
        ]
    ]


def test_marp_cli_convert_invokes_subprocess(
    test_settings: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    markdown_path = tmp_path / "slides.md"
    output_path = tmp_path / "output.pptx"
    markdown_path.write_text("---\nmarp: true\n---\n\n# Title", encoding="utf-8")
    calls: list[list[str]] = []

    monkeypatch.setattr("archium.infrastructure.renderers.marp_cli.shutil.which", lambda _: "marp")

    def fake_run(cmd: list[str], **kwargs: object) -> object:
        calls.append(cmd)
        return type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    monkeypatch.setattr("archium.infrastructure.renderers.marp_cli.subprocess.run", fake_run)

    runner = MarpCliRunner(test_settings)  # type: ignore[arg-type]
    result = runner.convert(markdown_path, output_path)

    assert result == output_path
    assert calls == [["marp", str(markdown_path), "-o", str(output_path)]]
