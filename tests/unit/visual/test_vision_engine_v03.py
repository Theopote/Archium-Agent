"""Vision Engine v0.3 — conditioned edit + input QA + soft harmonize."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from archium.application.visual.vision import (
    VisionImageEvaluator,
    VisionImageGenerationService,
    VisionPromptCompiler,
)
from archium.application.visual.vision.conditioned_editor import (
    ConditionedEditRequest,
    VisionConditionedEditor,
    soft_harmonize_png,
)
from archium.domain.visual.vision_generation import (
    ArchitectureImageType,
    ImageRequest,
    VisionGenerationMode,
    VisionStylePreset,
)
from archium.exceptions import WorkflowError


def test_evaluator_warns_on_soft_photo(tmp_path: Path) -> None:
    try:
        from PIL import Image, ImageFilter
    except ImportError:
        pytest.skip("Pillow unavailable")

    path = tmp_path / "soft.jpg"
    # Near-flat soft field → low Laplacian energy.
    Image.new("RGB", (320, 240), color=(180, 180, 180)).filter(ImageFilter.BLUR).save(path)
    report = VisionImageEvaluator().evaluate_base_image(path)
    assert report.blocking is False
    assert report.sharpness_passed is False
    assert report.warnings


def test_conditioned_editor_produces_png(tmp_path: Path) -> None:
    editor = VisionConditionedEditor()
    if not editor.is_available():
        pytest.skip("Pillow unavailable")

    from PIL import Image

    base = tmp_path / "site.jpg"
    Image.new("RGB", (400, 300), color=(120, 140, 160)).save(base)
    data = editor.edit(
        ConditionedEditRequest(
            base_image_path=str(base),
            width=640,
            height=360,
            subject="add covered walkway concept",
            mode=VisionGenerationMode.EDIT_FROM_PHOTO,
            style=VisionStylePreset.COMPETITION_CONCEPT_SKETCH.value,
            prompt_hash="edit01",
            overlay_cues=("风雨连廊",),
        )
    )
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(data) > 2000


def test_compiler_marks_edit_mode() -> None:
    request = ImageRequest(
        subject="renovation atmosphere with canopy",
        image_type=ArchitectureImageType.CONCEPT_SKETCH,
        mode=VisionGenerationMode.EDIT_FROM_PHOTO,
        base_image_path="/tmp/photo.jpg",
    )
    spec = VisionPromptCompiler().compile(request)
    assert spec.metadata.get("edit_mode") is True
    assert "Edit mode" in spec.prompt
    assert "as-built survey" in spec.negative_prompt or "evidence" in spec.negative_prompt


def test_service_edit_from_photo_persists(tmp_path: Path) -> None:
    from archium.config.settings import Settings
    from PIL import Image

    base = tmp_path / "photo.png"
    Image.new("RGB", (480, 320), color=(100, 110, 120)).save(base)
    settings = Settings(_env_file=None, project_storage_path=tmp_path / "storage")
    service = VisionImageGenerationService(session=None, settings=settings)
    result = service.generate(
        ImageRequest(
            subject="covered walkway renovation concept",
            image_type=ArchitectureImageType.CONCEPT_SKETCH,
            mode=VisionGenerationMode.EDIT_FROM_PHOTO,
            base_image_path=str(base),
            overlay_cues=["连廊"],
            width=640,
            height=360,
            harmonize_output=True,
        ),
        project_id=uuid4(),
        persist_asset=True,
    )
    assert result.success is True
    assert result.provider == "conditioned_editor"
    assert result.harmonized is True
    assert result.illustrative is True
    assert result.storage_path is not None
    assert result.input_evaluation is not None


def test_edit_mode_requires_base() -> None:
    from archium.config.settings import Settings

    service = VisionImageGenerationService(
        session=None,
        settings=Settings(_env_file=None, project_storage_path="/tmp"),
    )
    with pytest.raises(WorkflowError, match="base_image_path"):
        service.generate(
            ImageRequest(
                subject="missing base",
                mode=VisionGenerationMode.EDIT_FROM_PHOTO,
            )
        )


def test_soft_harmonize_preserves_png() -> None:
    from io import BytesIO

    from PIL import Image

    buf = BytesIO()
    Image.new("RGB", (32, 32), color=(200, 100, 50)).save(buf, format="PNG")
    out = soft_harmonize_png(buf.getvalue())
    assert out[:8] == b"\x89PNG\r\n\x1a\n"


def test_openai_edit_decodes_b64(tmp_path: Path) -> None:
    from archium.config.settings import Settings
    from archium.infrastructure.vision_gen.openai_compatible import (
        OpenAICompatibleVisionImageGenerator,
    )
    from PIL import Image

    base = tmp_path / "in.png"
    Image.new("RGB", (64, 64), color=(90, 90, 90)).save(base)

    class _Data:
        b64_json = (
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmM"
            "IQAAAABJRU5ErkJggg=="
        )

    class _Response:
        data = [_Data()]

    class _Images:
        def edit(self, **kwargs):
            assert "image" in kwargs
            return _Response()

        def generate(self, **kwargs):  # pragma: no cover
            raise AssertionError("generate should not be called")

    class _Client:
        images = _Images()

    settings = Settings(
        _env_file=None,
        vision_image_generation_enabled=True,
        vision_image_generation_provider="openai_compatible",
        vision_image_generation_api_key="test-key",
    )
    generator = OpenAICompatibleVisionImageGenerator(settings, client=_Client())
    spec = VisionPromptCompiler().compile(
        ImageRequest(
            subject="edit canopy",
            mode=VisionGenerationMode.EDIT_FROM_PHOTO,
            base_image_path=str(base),
        )
    )
    payload = generator.edit(spec, base_image_path=str(base))
    assert payload.provider == "openai_compatible"
    assert payload.data[:8] == b"\x89PNG\r\n\x1a\n"
