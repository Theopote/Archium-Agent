"""Reusable Streamlit UI components."""

from __future__ import annotations

from pathlib import Path

import streamlit as st


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
