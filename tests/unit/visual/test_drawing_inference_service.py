"""Unit tests for DrawingInferenceService."""

from __future__ import annotations

from archium.application.visual.drawing_inference_service import DrawingInferenceService
from archium.domain.visual.reference_slide import ReferenceElement, ReferenceElementType


def _image(**kwargs: object) -> ReferenceElement:
    defaults: dict[str, object] = {
        "id": "img1",
        "element_type": ReferenceElementType.IMAGE,
        "x": 0.6,
        "y": 1.2,
        "width": 5.5,
        "height": 3.8,
        "semantic_role": "hero_image",
    }
    defaults.update(kwargs)
    return ReferenceElement(**defaults)  # type: ignore[arg-type]


def _text(text: str, *, x: float, y: float, role: str = "body", **kwargs: object) -> ReferenceElement:
    defaults: dict[str, object] = {
        "id": f"t-{hash(text) % 10000}",
        "element_type": ReferenceElementType.TEXT,
        "x": x,
        "y": y,
        "width": 4.0,
        "height": 0.5,
        "text": text,
        "semantic_role": role,
        "font_size_pt": 14.0,
    }
    defaults.update(kwargs)
    return ReferenceElement(**defaults)  # type: ignore[arg-type]


def test_infer_drawing_from_neighbor_caption() -> None:
    image = _image()
    caption = _text("总平面图", x=0.6, y=5.1, role="caption")
    title = _text("总平面结构与关键指标", x=0.6, y=0.3, role="title", font_size_pt=24.0)
    result = DrawingInferenceService().infer(
        image,
        [title, caption],
        slide_title=title.text,
    )
    assert result.is_drawing is True
    assert any("neighbor" in e or "slide_title" in e for e in result.evidence)


def test_infer_drawing_from_shape_name_and_alt_without_picture_text() -> None:
    image = _image(source_shape_name="SitePlan_01", alt_text="院区总平面", text="")
    result = DrawingInferenceService().infer(image, [], slide_title="")
    assert image.text == ""
    assert result.is_drawing is True
    assert any("shape_name" in e or "alt_text" in e for e in result.evidence)


def test_photo_caption_not_promoted_to_drawing() -> None:
    image = _image(width=4.0, height=3.0)
    caption = _text("现场照片：入口拥堵", x=0.6, y=4.5, role="caption")
    result = DrawingInferenceService().infer(
        image,
        [caption],
        slide_title="入口现状问题",
    )
    assert result.is_drawing is False


def test_refine_slide_promotes_image_elements() -> None:
    image = _image(id="pic", text="")
    title = _text("首层平面与流线组织", x=0.5, y=0.3, role="title", font_size_pt=26.0)
    caption = _text("首层平面图", x=0.6, y=5.05, role="caption")
    elements = [title, image, caption]
    DrawingInferenceService().refine_slide_elements(elements, slide_title=title.text)
    assert image.element_type == ReferenceElementType.DRAWING
    assert image.semantic_role == "drawing"
