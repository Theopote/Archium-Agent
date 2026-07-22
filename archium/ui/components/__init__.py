"""Reusable Streamlit UI components."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from archium.ui.components.chrome import (
    render_danger_action,
    render_empty_state,
    render_error_callout,
    render_info_callout,
    render_inspector_section,
    render_page_header,
    render_panel,
    render_primary_action,
    render_secondary_action,
    render_section_label,
    render_status_badge,
    render_stepper,
    render_toolbar,
    render_warning_callout,
)

__all__ = [
    "render_danger_action",
    "render_download_button",
    "render_empty_state",
    "render_error_callout",
    "render_file_downloads",
    "render_info_callout",
    "render_inspector_section",
    "render_page_header",
    "render_panel",
    "render_primary_action",
    "render_secondary_action",
    "render_section_label",
    "render_status_badge",
    "render_stepper",
    "render_toolbar",
    "render_warning_callout",
]


def render_download_button(path: Path, *, key: str) -> None:
    if not path.is_file():
        return
    suffix = path.suffix.lower()
    mime = {
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".pdf": "application/pdf",
        ".json": "application/json",
        ".md": "text/markdown",
    }.get(suffix, "application/octet-stream")
    with path.open("rb") as handle:
        st.download_button(
            label=f"下载 {path.name}",
            data=handle.read(),
            file_name=path.name,
            mime=mime,
            key=key,
        )


def render_file_downloads(paths: list[Path], *, key_prefix: str) -> None:
    shown: set[str] = set()
    for index, path in enumerate(paths):
        normalized = str(path.resolve()) if path.exists() else str(path)
        if normalized in shown or not path.is_file():
            continue
        shown.add(normalized)
        render_download_button(path, key=f"{key_prefix}_{index}_{path.name}")
