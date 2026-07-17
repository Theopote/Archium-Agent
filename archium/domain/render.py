"""Unified render/export result for presentation artifacts."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class RenderResult:
    """Paths and metadata produced by JSON / Marp / binary export steps."""

    json_path: Path | None = None
    markdown_path: Path | None = None
    pptx_path: Path | None = None
    pdf_path: Path | None = None
    preview_images: list[Path] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @classmethod
    def from_state_paths(
        cls,
        *,
        json_path: Path | str | None = None,
        markdown_path: Path | str | None = None,
        pptx_path: Path | str | None = None,
        pdf_path: Path | str | None = None,
        preview_images: list[Path] | None = None,
        warnings: list[str] | None = None,
        marp_md_path: Path | str | None = None,
        marp_pptx_path: Path | str | None = None,
    ) -> RenderResult:
        """Build from workflow state or legacy field names."""
        md = markdown_path or marp_md_path
        pptx = pptx_path or marp_pptx_path
        return cls(
            json_path=_to_path(json_path),
            markdown_path=_to_path(md),
            pptx_path=_to_path(pptx),
            pdf_path=_to_path(pdf_path),
            preview_images=list(preview_images or []),
            warnings=list(warnings or []),
        )

    @property
    def marp_md_path(self) -> Path | None:
        return self.markdown_path

    @property
    def marp_pptx_path(self) -> Path | None:
        return self.pptx_path

    def output_paths(self) -> list[Path]:
        paths: list[Path] = []
        for candidate in (
            self.json_path,
            self.markdown_path,
            self.pptx_path,
            self.pdf_path,
            *self.preview_images,
        ):
            if candidate is not None:
                paths.append(candidate)
        return paths


def _to_path(value: Path | str | None) -> Path | None:
    if value is None:
        return None
    return value if isinstance(value, Path) else Path(str(value))
