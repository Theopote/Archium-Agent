"""Convert presentation domain models into Marp Markdown."""

from __future__ import annotations

from archium.domain.enums import SlideType
from archium.domain.presentation import PresentationBrief, Storyline
from archium.domain.slide import SlideSpec


def _escape_inline(text: str) -> str:
    return text.replace("|", "\\|")


def _format_citations(slide: SlideSpec) -> str:
    if not slide.source_citations:
        return ""
    lines = ["", "*来源：*"]
    for citation in slide.source_citations:
        page = f" p.{citation.page_number}" if citation.page_number else ""
        quote = f" — {citation.quote}" if citation.quote else ""
        lines.append(f"- {_escape_inline(citation.document_name)}{page}{quote}")
    return "\n".join(lines)


def _format_visual_requirements(slide: SlideSpec) -> str:
    if not slide.visual_requirements:
        return ""
    lines = ["", "*视觉需求：*"]
    for visual in slide.visual_requirements:
        required = "（必需）" if visual.required else "（可选）"
        lines.append(f"- {_escape_inline(visual.description)}{required}")
    return "\n".join(lines)


def _format_speaker_notes(slide: SlideSpec) -> str:
    if not slide.speaker_notes:
        return ""
    return (
        "\n\n<!--\n"
        "_speaker_note:\n"
        f"{slide.speaker_notes.strip()}\n"
        "-->"
    )


def _render_title_slide(brief: PresentationBrief) -> str:
    lines = [
        f"# {brief.title}",
        "",
        f"**汇报对象：** {_escape_inline(brief.audience)}",
        f"**汇报目的：** {_escape_inline(brief.purpose)}",
    ]
    if brief.core_message:
        lines.extend(["", f"**核心信息：** {_escape_inline(brief.core_message)}"])
    return "\n".join(lines)


def _render_thesis_slide(storyline: Storyline) -> str:
    return "\n".join(
        [
            "## 总体论点",
            "",
            storyline.thesis,
        ]
    )


def _render_slide(slide: SlideSpec) -> str:
    if slide.slide_type == SlideType.TITLE:
        body = [f"# {slide.title}"]
        if slide.message:
            body.extend(["", slide.message])
    elif slide.slide_type == SlideType.SECTION:
        body = [f"# {slide.title}"]
        if slide.message:
            body.extend(["", f"*{slide.message}*"])
    elif slide.slide_type in {SlideType.SUMMARY, SlideType.CLOSING}:
        body = [f"## {slide.title}", "", f"**{slide.message}**"]
    else:
        body = [f"## {slide.title}", "", f"**{slide.message}**"]
        if slide.key_points:
            body.append("")
            body.extend(f"- {_escape_inline(point)}" for point in slide.key_points)

    body.append(_format_visual_requirements(slide))
    body.append(_format_citations(slide))
    body.append(_format_speaker_notes(slide))
    return "\n".join(part for part in body if part)


def build_marp_markdown(
    brief: PresentationBrief,
    storyline: Storyline,
    slides: list[SlideSpec],
    *,
    theme: str = "default",
    paginate: bool = True,
) -> str:
    """Build a complete Marp Markdown document from presentation artifacts."""
    ordered_slides = sorted(slides, key=lambda slide: slide.order)
    sections: list[str] = [
        "---",
        "marp: true",
        f"theme: {theme}",
        f"paginate: {str(paginate).lower()}",
        "---",
        "",
        _render_title_slide(brief),
    ]

    if storyline.thesis.strip():
        sections.extend(["", "---", "", _render_thesis_slide(storyline)])

    for slide in ordered_slides:
        sections.extend(["", "---", "", _render_slide(slide)])

    return "\n".join(sections).strip() + "\n"
