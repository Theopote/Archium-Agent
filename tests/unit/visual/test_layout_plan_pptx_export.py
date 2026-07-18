"""Unit tests for LayoutPlan → PPTX instruction deck wiring."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from archium.config.settings import Settings
from archium.domain.visual import (
    LayoutElement,
    LayoutElementRole,
    LayoutFamily,
    LayoutPlan,
    default_presentation_design_system,
)
from archium.domain.visual.enums import LayoutContentType
from archium.exceptions import RenderingError
from archium.infrastructure.renderers.pptxgen.layout_plan_adapter import (
    PptxLayoutPlanAdapter,
    SlideContentBundle,
)
from archium.infrastructure.renderers.pptxgen_cli import PptxGenCliRunner
from archium.infrastructure.renderers.pptxgen_renderer import PptxGenPresentationRenderer


def _sample_plan(design_id) -> LayoutPlan:
    return LayoutPlan(
        slide_id=uuid4(),
        layout_family=LayoutFamily.TEXTUAL_ARGUMENT,
        layout_variant="lead_and_points",
        page_width=10,
        page_height=5.625,
        design_system_id=design_id,
        visual_intent_id=uuid4(),
        reading_order=["title", "body"],
        elements=[
            LayoutElement(
                id="title",
                role=LayoutElementRole.TITLE,
                content_type=LayoutContentType.TEXT,
                text_content="总平面确立轴线",
                x=0.7,
                y=0.45,
                width=8.6,
                height=0.5,
                style_token="title",
            ),
            LayoutElement(
                id="body",
                role=LayoutElementRole.BODY_TEXT,
                content_type=LayoutContentType.TEXT,
                text_content="通过交通重组改善院区体验。",
                x=0.7,
                y=1.2,
                width=8.6,
                height=2.0,
                style_token="body",
            ),
        ],
    )


def test_adapter_render_deck_preserves_coordinates() -> None:
    design = default_presentation_design_system()
    plan = _sample_plan(design.id)
    deck = PptxLayoutPlanAdapter().render_deck(
        title="测试汇报",
        slides=[(plan, design, SlideContentBundle(page_number=1))],
    )
    assert deck["schema"] == "archium.layout_instructions.v1"
    assert deck["slides"][0]["elements"][0]["x"] == 0.7
    assert deck["slides"][0]["elements"][0]["text"] == "总平面确立轴线"


def test_renderer_writes_deck_and_invokes_layout_cli(tmp_path: Path) -> None:
    design = default_presentation_design_system()
    plan = _sample_plan(design.id)
    renderer = PptxGenPresentationRenderer(Settings(_env_file=None))
    deck = renderer.build_layout_instruction_deck(
        title="测试汇报",
        plans=[plan],
        design_system=design,
    )

    pptx_path = tmp_path / "presentation.layout_plan.pptx"

    def _touch_output(*_args: object, **_kwargs: object) -> Path:
        pptx_path.write_bytes(b"pptx")
        return pptx_path.resolve()

    with patch.object(
        renderer._cli,
        "render_layout_instructions",
        side_effect=_touch_output,
    ) as mock_render:
        deck_path, rendered = renderer.export_pptx_from_layout_instructions(
            deck,
            output_dir=tmp_path,
        )

    assert deck_path.exists()
    payload = json.loads(deck_path.read_text(encoding="utf-8"))
    assert payload["slides"][0]["elements"][0]["x"] == 0.7
    assert rendered == pptx_path.resolve()
    mock_render.assert_called_once()


def test_cli_render_layout_instructions_invokes_render_plan(tmp_path: Path) -> None:
    deck_path = tmp_path / "presentation.layout_instructions.json"
    deck_path.write_text('{"title":"T","slides":[]}', encoding="utf-8")
    output_path = tmp_path / "out.pptx"
    script_path = tmp_path / "render.mjs"
    script_path.write_text("// mock", encoding="utf-8")
    plan_script = tmp_path / "render-plan.mjs"
    plan_script.write_text("// mock plan", encoding="utf-8")
    node_modules = tmp_path / "node_modules" / "pptxgenjs"
    node_modules.mkdir(parents=True)
    (node_modules / "package.json").write_text("{}", encoding="utf-8")

    settings = Settings(_env_file=None, pptxgen_script_path=script_path)
    runner = PptxGenCliRunner(settings)
    completed = MagicMock(returncode=0, stdout="", stderr="")

    def _touch_output(*_args: object, **_kwargs: object) -> MagicMock:
        output_path.write_bytes(b"pptx")
        return completed

    with (
        patch.object(runner, "is_available", return_value=True),
        patch(
            "archium.infrastructure.renderers.pptxgen_cli.subprocess.run",
            side_effect=_touch_output,
        ) as mock_run,
    ):
        result = runner.render_layout_instructions(deck_path, output_path)

    assert result == output_path.resolve()
    argv = mock_run.call_args[0][0]
    assert str(plan_script) in argv


def test_cli_render_layout_instructions_missing_script(tmp_path: Path) -> None:
    deck_path = tmp_path / "deck.json"
    deck_path.write_text("{}", encoding="utf-8")
    script_path = tmp_path / "render.mjs"
    script_path.write_text("// mock", encoding="utf-8")
    settings = Settings(_env_file=None, pptxgen_script_path=script_path)
    runner = PptxGenCliRunner(settings)
    with pytest.raises(RenderingError, match="LayoutPlan render script"):
        runner.render_layout_instructions(deck_path, tmp_path / "out.pptx")
