"""Text run PPTX adapter + Studio set_text_runs command."""

from __future__ import annotations

from uuid import uuid4

from archium.application.visual.studio_command_executor import (
    StudioCommandExecutor,
    StudioExecutionContext,
)
from archium.domain.visual.render_scene import (
    BackgroundStyle,
    RenderScene,
    TextNode,
    TextRun,
)
from archium.domain.visual.studio_command import RewriteTextCommand, SetTextRunsCommand
from archium.infrastructure.renderers.scene_pptx_adapter import RenderScenePptxAdapter


def _scene(node: TextNode) -> RenderScene:
    return RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=10,
        page_height=5.625,
        background=BackgroundStyle(color="#FFFFFF"),
        nodes=[node],
    )


def _ctx(scene: RenderScene) -> StudioExecutionContext:
    return StudioExecutionContext(presentation_id=uuid4(), validate_asset_bindings=False)


def test_adapter_emits_runs_for_mixed_weight_title() -> None:
    scene = _scene(
        TextNode(
            id="title",
            x=0.7,
            y=0.5,
            width=8,
            height=0.7,
            text="院区 Title",
            font_family="Arial",
            font_family_cjk="Microsoft YaHei",
            font_size=32,
            font_weight=400,
            color="#1A1A1A",
            line_height=1.35,
            semantic_role="title",
            runs=[
                TextRun(text="院区", font_weight=700, color="#1A1A1A"),
                TextRun(text=" Title", font_weight=400, color="#666666"),
            ],
        )
    )
    instruction = RenderScenePptxAdapter().render_slide(scene)
    element = next(item for item in instruction.elements if item["id"] == "title")
    assert element["text"] == "院区 Title"
    assert len(element["runs"]) == 2
    assert element["runs"][0]["font_weight"] == 700
    assert element["runs"][1]["font_weight"] == 400
    assert element["runs"][1]["color"] == "666666"


def test_adapter_emits_run_tracking_opacity_outline() -> None:
    scene = _scene(
        TextNode(
            id="title",
            x=0.7,
            y=0.5,
            width=8,
            height=1.2,
            text="航运",
            font_family="Arial",
            font_family_cjk="Microsoft YaHei",
            font_size=28,
            font_weight=300,
            color="#1A1A1A",
            line_height=1.2,
            semantic_role="title",
            rotation=-90.0,
            runs=[
                TextRun(
                    text="航运",
                    font_size=48.0,
                    font_weight=300,
                    letter_spacing=0.14,
                    opacity=0.92,
                    outline=True,
                    outline_width_pt=1.2,
                    outline_color="#1A1A1A",
                    fill_enabled=False,
                )
            ],
        )
    )
    instruction = RenderScenePptxAdapter().render_slide(scene)
    element = next(item for item in instruction.elements if item["id"] == "title")
    assert element["rotation"] == -90.0
    run = element["runs"][0]
    assert run["letter_spacing"] == 0.14
    assert run["opacity"] == 0.92
    assert run["outline"] is True
    assert run["fill_enabled"] is False



def test_set_text_runs_command_round_trips() -> None:
    scene = _scene(
        TextNode(
            id="title",
            x=0.5,
            y=0.5,
            width=6,
            height=0.6,
            text="旧标题",
            font_family="Arial",
            font_size=24,
            color="#111111",
            line_height=1.2,
        )
    )
    result = StudioCommandExecutor().execute(
        scene,
        SetTextRunsCommand(
            presentation_id=uuid4(),
            slide_id=scene.slide_id,
            node_id="title",
            runs=[
                {"text": "结论", "font_weight": 700, "color": "#111111"},
                {"text": " Claim", "font_weight": 400, "color": "#555555"},
            ],
        ),
        _ctx(scene),
    )
    assert result.success is True
    assert result.candidate_scene is not None
    node = result.candidate_scene.node_by_id("title")
    assert isinstance(node, TextNode)
    assert node.text == "结论 Claim"
    assert len(node.runs) == 2
    assert node.runs[0].font_weight == 700


def test_rewrite_text_collapses_existing_runs() -> None:
    scene = _scene(
        TextNode(
            id="title",
            x=0.5,
            y=0.5,
            width=6,
            height=0.6,
            text="A B",
            font_family="Arial",
            font_size=24,
            color="#111111",
            line_height=1.2,
            runs=[
                TextRun(text="A", font_weight=700),
                TextRun(text=" B", font_weight=400),
            ],
        )
    )
    result = StudioCommandExecutor().execute(
        scene,
        RewriteTextCommand(
            presentation_id=uuid4(),
            slide_id=scene.slide_id,
            node_id="title",
            new_text="整框新文案",
        ),
        _ctx(scene),
    )
    assert result.success is True
    node = result.candidate_scene.node_by_id("title") if result.candidate_scene else None
    assert isinstance(node, TextNode)
    assert node.text == "整框新文案"
    assert len(node.runs) == 1
    assert node.runs[0].font_weight == 700
