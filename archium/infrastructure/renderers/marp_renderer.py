"""Marp renderer for SlideSpec-based presentation exports."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from archium.config.settings import Settings, get_settings
from archium.domain.presentation import PresentationBrief, Storyline
from archium.domain.slide import SlideSpec
from archium.infrastructure.renderers.marp_cli import MarpCliRunner
from archium.infrastructure.renderers.marp_markdown import build_marp_markdown


class MarpPresentationRenderer:
    """Export brief/storyline/slides as Marp Markdown and optional PPTX/PDF."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        theme: str = "default",
        paginate: bool = True,
    ) -> None:
        self._settings = settings or get_settings()
        self._theme = theme
        self._paginate = paginate
        self._cli = MarpCliRunner(self._settings)

    def output_dir(self, presentation_id: UUID, version: int = 1) -> Path:
        return (
            self._settings.output_path
            / "presentations"
            / str(presentation_id)
            / f"v{version}"
        )

    def render(
        self,
        *,
        presentation_id: UUID,
        brief: PresentationBrief,
        storyline: Storyline,
        slides: list[SlideSpec],
        version: int = 1,
    ) -> Path:
        """Write presentation.md and return its path."""
        output_dir = self.output_dir(presentation_id, version)
        output_dir.mkdir(parents=True, exist_ok=True)
        markdown_path = output_dir / "presentation.md"
        markdown_path.write_text(
            build_marp_markdown(
                brief,
                storyline,
                slides,
                theme=self._theme,
                paginate=self._paginate,
            ),
            encoding="utf-8",
        )
        return markdown_path

    def export_pptx(
        self,
        markdown_path: Path,
        *,
        output_path: Path | None = None,
    ) -> Path:
        target = output_path or markdown_path.with_suffix(".pptx")
        return self._cli.convert(markdown_path, target)

    def export_pdf(
        self,
        markdown_path: Path,
        *,
        output_path: Path | None = None,
    ) -> Path:
        target = output_path or markdown_path.with_suffix(".pdf")
        return self._cli.convert(markdown_path, target)

    def render_and_export_pptx(
        self,
        *,
        presentation_id: UUID,
        brief: PresentationBrief,
        storyline: Storyline,
        slides: list[SlideSpec],
        version: int = 1,
    ) -> tuple[Path, Path]:
        """Write Markdown and export PPTX in one step."""
        markdown_path = self.render(
            presentation_id=presentation_id,
            brief=brief,
            storyline=storyline,
            slides=slides,
            version=version,
        )
        pptx_path = self.export_pptx(markdown_path)
        return markdown_path, pptx_path
