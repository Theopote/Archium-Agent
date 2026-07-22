"""Unit tests for single-page partial-edit preservation rules."""

from __future__ import annotations

from uuid import uuid4

import pytest
from archium.application.visual.asset_path_resolver import project_asset_uri
from archium.application.visual.partial_edit_preservation import (
    assert_partial_edit_preservation,
    evaluate_partial_edit_preservation,
)
from archium.application.visual.scene_proposal_service import SceneProposalService
from archium.application.visual.studio_command_executor import (
    StudioCommandExecutor,
    StudioExecutionContext,
)
from archium.domain.citation import Citation
from archium.domain.slide import SlideSpec
from archium.domain.visual.partial_edit_preservation import (
    PARTIAL_EDIT_INTERACTION_RULE,
    PartialEditPreservationRule,
)
from archium.domain.visual.render_scene import (
    BackgroundStyle,
    ImageNode,
    RenderScene,
    TextNode,
)
from archium.domain.visual.studio_command import ReplaceAssetCommand, RewriteTextCommand
from archium.exceptions import WorkflowError


def _text(*, node_id: str, text: str, locked: bool = False, role: str = "") -> TextNode:
    return TextNode(
        id=node_id,
        x=0.5,
        y=1.0,
        width=4.0,
        height=0.5,
        z_index=1,
        text=text,
        font_family="Arial",
        font_size=14,
        color="#000000",
        line_height=1.2,
        locked=locked,
        semantic_role=role,
    )


def _image(*, node_id: str, asset_id) -> ImageNode:
    uri = project_asset_uri(asset_id)
    return ImageNode(
        id=node_id,
        x=1.0,
        y=2.0,
        width=3.0,
        height=2.0,
        z_index=1,
        storage_uri=uri,
        asset_path=uri,
        asset_id=asset_id,
        asset_origin="project_upload",
    )


def _scene(*nodes) -> RenderScene:
    return RenderScene(
        slide_id=uuid4(),
        layout_plan_id=uuid4(),
        page_width=10,
        page_height=5.625,
        background=BackgroundStyle(color="#FFFFFF"),
        nodes=list(nodes),
    )


def test_rewrite_preserves_unspecified_and_assets() -> None:
    asset_id = uuid4()
    base = _scene(
        _text(node_id="title", text="旧标题"),
        _text(node_id="body", text="正文不变"),
        _image(node_id="photo", asset_id=asset_id),
    )
    presentation_id = uuid4()
    command = RewriteTextCommand(
        presentation_id=presentation_id,
        slide_id=base.slide_id,
        node_id="title",
        new_text="新标题",
        target_node_ids=["title"],
        reason=PARTIAL_EDIT_INTERACTION_RULE,
    )
    result = StudioCommandExecutor().execute(
        base,
        command,
        StudioExecutionContext(presentation_id=presentation_id),
    )
    assert result.success and result.candidate_scene is not None

    report = assert_partial_edit_preservation(
        base,
        result.candidate_scene,
        commands=[command],
        patch_actions=list(result.applied_actions),
    )
    assert report.ok
    assert "body" not in report.changed_node_ids
    assert "photo" not in report.changed_node_ids
    assert report.interaction_rule == PARTIAL_EDIT_INTERACTION_RULE


def test_unspecified_node_mutation_is_rejected() -> None:
    base = _scene(
        _text(node_id="title", text="标题"),
        _text(node_id="body", text="正文"),
    )
    proposed = base.model_copy(deep=True)
    for node in proposed.nodes:
        if node.id == "body" and isinstance(node, TextNode):
            node.text = "被偷偷改掉"

    command = RewriteTextCommand(
        presentation_id=uuid4(),
        slide_id=base.slide_id,
        node_id="title",
        new_text="标题",
        target_node_ids=["title"],
    )
    report = evaluate_partial_edit_preservation(base, proposed, commands=[command])
    assert not report.ok
    assert any(
        item.rule == PartialEditPreservationRule.UNSPECIFIED_NODES_UNCHANGED
        for item in report.violations
    )


def test_locked_node_mutation_is_rejected() -> None:
    base = _scene(_text(node_id="title", text="锁定标题", locked=True))
    proposed = base.model_copy(deep=True)
    for node in proposed.nodes:
        if isinstance(node, TextNode):
            node.text = "改了锁定标题"
            node.locked = True

    command = RewriteTextCommand(
        presentation_id=uuid4(),
        slide_id=base.slide_id,
        node_id="title",
        new_text="改了锁定标题",
        target_node_ids=["title"],
    )
    with pytest.raises(WorkflowError, match="锁定节点"):
        assert_partial_edit_preservation(base, proposed, commands=[command])


def test_asset_identity_protected_without_replace_command() -> None:
    old_id = uuid4()
    new_id = uuid4()
    base = _scene(_image(node_id="photo", asset_id=old_id))
    proposed = base.model_copy(deep=True)
    for node in proposed.nodes:
        if isinstance(node, ImageNode):
            node.asset_id = new_id
            node.storage_uri = project_asset_uri(new_id)
            node.asset_path = node.storage_uri

    command = RewriteTextCommand(
        presentation_id=uuid4(),
        slide_id=base.slide_id,
        node_id="title",
        new_text="x",
        target_node_ids=["title"],
    )
    report = evaluate_partial_edit_preservation(base, proposed, commands=[command])
    assert any(
        item.rule == PartialEditPreservationRule.ASSET_IDENTITY_UNCHANGED
        for item in report.violations
    )


def test_explicit_replace_allows_asset_change() -> None:
    old_id = uuid4()
    new_id = uuid4()
    base = _scene(_image(node_id="photo", asset_id=old_id))
    presentation_id = uuid4()
    command = ReplaceAssetCommand(
        presentation_id=presentation_id,
        slide_id=base.slide_id,
        node_id="photo",
        asset_id=new_id,
        storage_uri=project_asset_uri(new_id),
        target_node_ids=["photo"],
    )
    result = StudioCommandExecutor().execute(
        base,
        command,
        StudioExecutionContext(presentation_id=presentation_id),
    )
    assert result.success and result.candidate_scene is not None
    report = assert_partial_edit_preservation(
        base,
        result.candidate_scene,
        commands=[command],
        patch_actions=list(result.applied_actions),
    )
    assert report.ok


def test_citations_and_facts_protected_on_slide_spec() -> None:
    base = _scene(_text(node_id="title", text="标题"))
    proposed = base.model_copy(deep=True)
    for node in proposed.nodes:
        if isinstance(node, TextNode):
            node.text = "新标题"
    slide_before = SlideSpec(
        presentation_id=uuid4(),
        chapter_id="ch1",
        order=0,
        title="标题",
        message="原结论",
        key_points=["要点A"],
        source_citations=[
            Citation(
                document_id=uuid4(),
                document_name="报告.pdf",
                page_number=3,
                quote="证据",
            )
        ],
    )
    slide_after = slide_before.model_copy(
        update={
            "message": "被改结论",
            "source_citations": [],
        }
    )
    command = RewriteTextCommand(
        presentation_id=uuid4(),
        slide_id=base.slide_id,
        node_id="title",
        new_text="新标题",
        target_node_ids=["title"],
    )
    report = evaluate_partial_edit_preservation(
        base,
        proposed,
        commands=[command],
        slide_before=slide_before,
        slide_after=slide_after,
    )
    rules = {item.rule for item in report.violations}
    assert PartialEditPreservationRule.PAGE_FACTS_UNCHANGED in rules
    assert PartialEditPreservationRule.CITATIONS_UNCHANGED in rules


def test_create_proposal_embeds_preservation_report() -> None:
    base = _scene(
        _text(node_id="title", text="旧标题"),
        _text(node_id="body", text="正文"),
    )
    presentation_id = uuid4()
    service = SceneProposalService.__new__(SceneProposalService)
    service._executor = StudioCommandExecutor()
    service._scenes = None  # type: ignore[assignment]
    service._proposals = None  # type: ignore[assignment]
    service._presentations = None  # type: ignore[assignment]
    service._scene_history = None  # type: ignore[assignment]
    service._studio_scene = None  # type: ignore[assignment]
    service._settings = None  # type: ignore[assignment]
    service._session = None  # type: ignore[assignment]

    # Bypass QA helpers that need DB/settings.
    service._qa_for_scene = lambda *args, **kwargs: type(  # type: ignore[method-assign]
        "QA",
        (),
        {"issues": [], "layers": {}, "preview_render_success": True},
    )()
    service._project_id_for_presentation = lambda _pid: None  # type: ignore[method-assign]

    proposal = service.create_proposal(
        base_scene=base,
        commands=[
            RewriteTextCommand(
                presentation_id=presentation_id,
                slide_id=base.slide_id,
                node_id="title",
                new_text="新标题",
                target_node_ids=["title"],
            )
        ],
        presentation_id=presentation_id,
        slide_id=base.slide_id,
    )
    assert proposal.preservation is not None
    assert proposal.preservation.ok
    assert PARTIAL_EDIT_INTERACTION_RULE in proposal.reasons
