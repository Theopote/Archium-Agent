"""Unit tests for PlaceholderBindingSignature match priority."""

from __future__ import annotations

from archium.application.visual.placeholder_binding_matcher import (
    match_placeholder,
    score_placeholder_candidate,
)
from archium.application.visual.placeholder_binding_normalize import (
    build_placeholder_binding_signature,
    semantic_role_from_placeholder_type,
)
from archium.domain.visual.placeholder_binding import (
    PLACEHOLDER_MATCH_PRIORITY,
    PlaceholderBindingSignature,
    PlaceholderBindingTarget,
)
from archium.domain.visual.reference_slide import ReferenceElement, ReferenceElementType


def _element(
    *,
    element_id: str,
    role: str = "body",
    ptype: str = "BODY",
    name: str = "",
    idx: int | None = None,
    x: float = 1.0,
    y: float = 1.0,
    width: float = 4.0,
    height: float = 1.0,
) -> ReferenceElement:
    binding = PlaceholderBindingSignature(
        placeholder_idx=idx,
        placeholder_name=name,
        placeholder_type=ptype,
        semantic_role=role,
        fallback_matchers=[f"role:{role}", f"type:{ptype}"],
    )
    return ReferenceElement(
        id=element_id,
        element_type=ReferenceElementType.PLACEHOLDER,
        x=x,
        y=y,
        width=width,
        height=height,
        semantic_role=role,
        source_shape_name=name,
        placeholder_binding=binding,
    )


def test_match_priority_order_documented() -> None:
    assert PLACEHOLDER_MATCH_PRIORITY[0] == "semantic_role"
    assert PLACEHOLDER_MATCH_PRIORITY[-1] == "placeholder_idx"


def test_semantic_role_beats_index() -> None:
    title = _element(element_id="a", role="title", ptype="TITLE", name="Title 1", idx=99)
    body = _element(element_id="b", role="body", ptype="BODY", name="Content", idx=0)
    target = PlaceholderBindingTarget(semantic_role="title", preferred_idx=0)
    result = match_placeholder([body, title], target)
    assert result is not None
    assert result.element.id == "a"
    assert result.matched_by == "semantic_role"


def test_type_used_when_role_missing() -> None:
    candidate = _element(
        element_id="pic",
        role="",
        ptype="PICTURE",
        name="Picture Placeholder 2",
        idx=10,
    )
    # Clear role so type becomes the primary signal.
    candidate.placeholder_binding = PlaceholderBindingSignature(
        placeholder_idx=10,
        placeholder_name="Picture Placeholder 2",
        placeholder_type="PICTURE",
        semantic_role="",
        fallback_matchers=["type:PICTURE", "name:picture placeholder 2", "idx:10"],
    )
    target = PlaceholderBindingTarget(
        semantic_role="hero_image",
        preferred_types=["PICTURE"],
    )
    score, matched_by = score_placeholder_candidate(
        candidate.placeholder_binding,
        candidate,
        target,
    )
    assert score >= 15.0
    assert matched_by == "placeholder_type"


def test_name_beats_index_when_type_absent() -> None:
    named = _element(
        element_id="named",
        role="body",
        ptype="",
        name="Project Title Box",
        idx=7,
    )
    other = _element(
        element_id="other",
        role="body",
        ptype="",
        name="TextBox 3",
        idx=0,
    )
    target = PlaceholderBindingTarget(
        semantic_role="body",
        preferred_names=["Project Title Box"],
        preferred_idx=0,
    )
    result = match_placeholder([other, named], target)
    assert result is not None
    assert result.element.id == "named"


def test_geometry_similarity_helps_disambiguate() -> None:
    near = _element(element_id="near", role="body", x=0.5, y=0.4, width=8.0, height=1.0)
    far = _element(element_id="far", role="body", x=7.0, y=4.0, width=2.0, height=0.5)
    target = PlaceholderBindingTarget(
        semantic_role="body",
        x=0.4,
        y=0.35,
        width=8.2,
        height=1.1,
    )
    result = match_placeholder([far, near], target)
    assert result is not None
    assert result.element.id == "near"


def test_build_signature_upgrades_placeholder_role() -> None:
    sig = build_placeholder_binding_signature(
        placeholder_idx=0,
        placeholder_name="Title 1",
        placeholder_type="CENTER_TITLE",
        semantic_role="placeholder",
        x=0.5,
        y=0.3,
        width=9.0,
        height=1.0,
    )
    assert sig.semantic_role == "title"
    assert sig.placeholder_type == "CENTER_TITLE"
    assert sig.fallback_matchers[0].startswith("role:")
    assert any(item.startswith("idx:") for item in sig.fallback_matchers)


def test_picture_type_maps_to_image_role() -> None:
    assert semantic_role_from_placeholder_type("PICTURE") == "hero_image"
    assert (
        semantic_role_from_placeholder_type(
            "PICTURE",
            height=1.5,
            page_height=5.625,
        )
        == "supporting_image"
    )
