"""RS-006: Template Studio compile path uses SceneCompilerChain."""

from __future__ import annotations

from pathlib import Path


def test_template_studio_fill_preview_uses_scene_compiler_chain() -> None:
    source = Path(
        "archium/application/visual/template_studio_service.py"
    ).read_text(encoding="utf-8")
    assert "SceneCompilerChain" in source
    assert "SceneCompileContext" in source
    assert "RenderSceneCompiler().compile" not in source
