"""Export authority vocabulary (DOM-003).

Formal editable PPTX delivery recognizes **RenderScene** only.
``PresentationSpec`` is a legacy derived artifact for template-compat exports
and tests — never a second formal SSOT.
"""

from __future__ import annotations

from enum import StrEnum


class FormalExportAuthority(StrEnum):
    """Authority for client-facing editable PPTX / formal delivery."""

    RENDER_SCENE = "render_scene"


class DerivedExportKind(StrEnum):
    """Non-formal / compatibility export kinds."""

    PRESENTATION_SPEC = "presentation_spec"
    LAYOUT_PLAN_INSTRUCTIONS = "layout_plan_instructions"


# Machine-readable SSOT for architecture contracts and gates.
FORMAL_EDITABLE_PPTX_AUTHORITY = FormalExportAuthority.RENDER_SCENE

# Human-facing roles (content → compile → render/edit → legacy derive).
CONTENT_EXPRESSION_AUTHORITY = "slide_spec"
GEOMETRY_COMPILE_AUTHORITY = "layout_plan"
RENDER_EDIT_AUTHORITY = FormalExportAuthority.RENDER_SCENE.value
LEGACY_TEMPLATE_EXPORT_KIND = DerivedExportKind.PRESENTATION_SPEC.value


def is_formal_editable_pptx_authority(value: str | FormalExportAuthority) -> bool:
    raw = value.value if isinstance(value, FormalExportAuthority) else str(value)
    return raw == FORMAL_EDITABLE_PPTX_AUTHORITY.value
