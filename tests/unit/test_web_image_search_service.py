"""Tests for web image search orchestration."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from archium.config.settings import Settings
from archium.domain.enums import VisualType
from archium.domain.slide import SlideSpec, VisualRequirement
from archium.infrastructure.images.web_search.pexels import PexelsClient
from archium.infrastructure.images.web_search.service import WebImageSearchService, _NamedProvider


def test_web_search_downloads_first_valid_candidate(tmp_path: Path) -> None:
    slide_id = uuid4()
    slide = SlideSpec(
        id=slide_id,
        presentation_id=uuid4(),
        chapter_id="ch1",
        order=0,
        title="夜景效果图",
        message="展示灯光",
        visual_requirements=[
            VisualRequirement(
                type=VisualType.RENDERING,
                description="夜景透视",
                required=True,
            )
        ],
    )

    def fake_fetch_json(url: str, headers: dict[str, str], timeout: float) -> dict:
        return {
            "photos": [
                {
                    "photographer": "Alex",
                    "url": "https://www.pexels.com/photo/1/",
                    "src": {"large": "https://images.pexels.com/photos/1.jpeg"},
                }
            ]
        }

    def fake_fetch_bytes(url: str, timeout: float) -> bytes:
        return b"\xff\xd8\xff\xd9"

    settings = Settings(
        _env_file=None,
        web_image_search_enabled=True,
        pexels_api_key="test-key",
    )
    service = WebImageSearchService(
        settings,
        providers=[_NamedProvider("pexels", PexelsClient("test-key", fetch_json=fake_fetch_json))],
    )

    from archium.infrastructure.images.web_search import service as web_service

    original_download = web_service.download_image

    def patched_download(url: str, dest: Path, **kwargs):
        kwargs.pop("fetch_bytes", None)
        return original_download(url, dest, fetch_bytes=fake_fetch_bytes, **kwargs)

    web_service.download_image = patched_download  # type: ignore[assignment]
    try:
        result = service.resolve_requirement(
            slide,
            slide.visual_requirements[0],
            0,
            output_dir=tmp_path,
        )
    finally:
        web_service.download_image = original_download

    assert result is not None
    assert result.web_sourced is True
    assert result.path.exists()
    assert "Alex" in (result.attribution or "")


def test_web_search_skips_site_plan_requirements() -> None:
    slide = SlideSpec(
        id=uuid4(),
        presentation_id=uuid4(),
        chapter_id="ch1",
        order=0,
        title="总图",
        message="交通",
        visual_requirements=[
            VisualRequirement(
                type=VisualType.SITE_PLAN,
                description="总平面图",
                required=True,
            )
        ],
    )
    settings = Settings(_env_file=None, web_image_search_enabled=True, pexels_api_key="key")
    service = WebImageSearchService(settings)
    assert service.can_search(VisualType.SITE_PLAN) is False
    assert service.resolve_requirement(slide, slide.visual_requirements[0], 0, output_dir=Path(".")) is None


def test_search_candidates_returns_without_download() -> None:
    from archium.infrastructure.images.web_search.models import WebImageCandidate

    slide = SlideSpec(
        id=uuid4(),
        presentation_id=uuid4(),
        chapter_id="ch1",
        order=0,
        title="效果图",
        message="入口",
        visual_requirements=[
            VisualRequirement(
                type=VisualType.RENDERING,
                description="透视",
                required=True,
            )
        ],
    )

    class FakeProvider:
        provider_name = "pexels"

        def search(self, query: str, *, per_page: int = 5):
            return [
                WebImageCandidate(
                    download_url="https://images.pexels.com/photos/1.jpeg",
                    page_url="https://www.pexels.com/photo/1/",
                    attribution="Photo by Alex on Pexels",
                )
            ]

    settings = Settings(_env_file=None, web_image_search_enabled=True, pexels_api_key="key")
    service = WebImageSearchService(settings, providers=[FakeProvider()])  # type: ignore[list-item]
    query, items = service.search_candidates(slide, slide.visual_requirements[0], limit=3)
    assert "透视" in query
    assert len(items) == 1
    assert items[0][0] == "pexels"
