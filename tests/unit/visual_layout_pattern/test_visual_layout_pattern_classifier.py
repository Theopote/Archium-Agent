"""Tests for VisualLayoutPatternClassifier."""

from __future__ import annotations

from archium.application.visual.functional_slide_classifier import FunctionalSlideClassifier
from archium.application.visual.visual_layout_pattern_classifier import (
    VisualLayoutPatternClassifier,
    extract_visual_layout_features,
)
from archium.domain.visual.reference_slide import (
    ReferenceElement,
    ReferenceElementType,
    ReferenceSlideSnapshot,
)
from archium.domain.visual.template_induction import (
    ArchitecturalContentType,
    FunctionalSlideType,
    VisualLayoutPattern,
)


def _slide(
    *,
    slide_id: str = "slide_001",
    elements: list[ReferenceElement] | None = None,
    embedding: list[float] | None = None,
    text: list[str] | None = None,
) -> ReferenceSlideSnapshot:
    return ReferenceSlideSnapshot(
        slide_index=0,
        slide_id=slide_id,
        elements=elements or [],
        text_content=text or [],
        visual_embedding=embedding,
    )


def test_classify_image_grid_from_multiple_images() -> None:
    slide = _slide(
        elements=[
            ReferenceElement(
                id="t1",
                element_type=ReferenceElementType.TEXT,
                x=0.5,
                y=0.3,
                width=8,
                height=0.5,
                text="现场问题",
            ),
            ReferenceElement(
                id="i1",
                element_type=ReferenceElementType.IMAGE,
                x=0.5,
                y=1.0,
                width=2.5,
                height=1.5,
            ),
            ReferenceElement(
                id="i2",
                element_type=ReferenceElementType.IMAGE,
                x=3.2,
                y=1.0,
                width=2.5,
                height=1.5,
            ),
            ReferenceElement(
                id="i3",
                element_type=ReferenceElementType.IMAGE,
                x=5.9,
                y=1.0,
                width=2.5,
                height=1.5,
            ),
        ],
        embedding=[0.5, 0.2, 0.2, 0.2, 0.375, 0.1, 0, 0, 0.08, 0, 0, 0.2],
        text=["现场问题"],
    )
    pattern, confidence, _ = VisualLayoutPatternClassifier().classify(
        slide,
        functional_type=FunctionalSlideType.CONTENT,
        content_type=ArchitecturalContentType.PHOTO_ANALYSIS,
    )
    assert pattern == VisualLayoutPattern.IMAGE_GRID
    assert confidence >= 0.7


def test_classify_full_bleed_drawing() -> None:
    slide = _slide(
        elements=[
            ReferenceElement(
                id="d1",
                element_type=ReferenceElementType.DRAWING,
                x=0.4,
                y=0.8,
                width=8.5,
                height=4.2,
            )
        ],
        embedding=[0.7, 0.1, 0.1, 0.72, 0.125, 0.05, 0, 0, 0, 0, 0.33, 0.05],
    )
    pattern, _, _ = VisualLayoutPatternClassifier().classify(
        slide,
        functional_type=FunctionalSlideType.CONTENT,
        content_type=ArchitecturalContentType.DRAWING_FOCUS,
    )
    assert pattern == VisualLayoutPattern.FULL_BLEED_DRAWING


def test_classify_two_column_from_left_heavy_embedding() -> None:
    slide = _slide(
        elements=[
            ReferenceElement(
                id="img",
                element_type=ReferenceElementType.IMAGE,
                x=0.5,
                y=1.0,
                width=4.0,
                height=3.0,
            ),
            ReferenceElement(
                id="body",
                element_type=ReferenceElementType.TEXT,
                x=5.0,
                y=1.0,
                width=4.0,
                height=2.5,
                text="说明文字",
            ),
        ],
        embedding=[0.45, 0.15, 0.35, 0.28, 0.125, 0.2, 0, 0, 0.08, 0, 0, 0.1],
        text=["说明文字"],
    )
    pattern, _, _ = VisualLayoutPatternClassifier().classify(
        slide,
        functional_type=FunctionalSlideType.CONTENT,
        content_type=ArchitecturalContentType.IMAGE_TEXT_HYBRID,
    )
    assert pattern == VisualLayoutPattern.TWO_COLUMN


def test_classify_all_enriches_functional_classifications() -> None:
    slide = _slide(
        elements=[
            ReferenceElement(
                id="hero",
                element_type=ReferenceElementType.IMAGE,
                x=1.0,
                y=0.8,
                width=7.5,
                height=4.0,
            )
        ],
        embedding=[0.55, 0.2, 0.1, 0.58, 0.125, 0.02, 0, 0, 0, 0, 0, 0.05],
    )
    base = FunctionalSlideClassifier().classify(slide, deck_size=1)
    enriched = VisualLayoutPatternClassifier().classify_all([slide], [base])[0]
    assert enriched.visual_layout_pattern == VisualLayoutPattern.HERO_IMAGE


def test_extract_features_uses_embedding_when_present() -> None:
    slide = _slide(embedding=[0.1, 0.2, 0.3, 0.4, 0, 0, 0, 0, 0, 0, 0, 0])
    features = extract_visual_layout_features(slide)
    assert features.covered == 0.1
    assert features.left_heavy == 0.3
    assert features.max_element == 0.4
