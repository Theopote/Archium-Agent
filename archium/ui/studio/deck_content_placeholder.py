"""Content placeholder cards for deck overview when layout preview is missing."""

from __future__ import annotations

import html

from archium.domain.slide import SlideSpec
from archium.ui.label_map import slide_role_label


def content_placeholder_html(
    *,
    index: int,
    slide: SlideSpec,
    accent_color: str,
) -> str:
    title = html.escape((slide.title or f"P{index + 1}").strip())
    message = html.escape((slide.message or "内容待补充").strip()[:90])
    role = html.escape(slide_role_label(getattr(slide, "slide_role", None)))
    return (
        f'<div style="aspect-ratio:16/9;background:linear-gradient(165deg,#faf9f7 0%,#f4f2ee 100%);'
        f'border:1px solid #e0ddd6;border-radius:6px;padding:8% 9%;box-sizing:border-box;'
        f'display:flex;flex-direction:column;justify-content:space-between;">'
        f'<div style="font-size:0.62rem;font-weight:600;letter-spacing:0.04em;color:#8a8780;">'
        f"P{index + 1} · {role} · 内容占位</div>"
        f'<div style="font-size:0.82rem;font-weight:600;color:#2a241f;line-height:1.25;">{title}</div>'
        f'<div style="font-size:0.72rem;color:#5a5248;line-height:1.35;">{message}</div>'
        f'<div style="height:3px;background:{html.escape(accent_color)};border-radius:2px;"></div>'
        f"</div>"
    )
