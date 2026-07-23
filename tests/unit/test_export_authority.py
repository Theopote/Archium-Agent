"""DOM-003 formal export authority and Spec demotion."""

from __future__ import annotations

from archium.domain import presentation_spec as presentation_spec_module
from archium.domain.export_authority import (
    CONTENT_EXPRESSION_AUTHORITY,
    FORMAL_EDITABLE_PPTX_AUTHORITY,
    GEOMETRY_COMPILE_AUTHORITY,
    LEGACY_TEMPLATE_EXPORT_KIND,
    RENDER_EDIT_AUTHORITY,
    DerivedExportKind,
    FormalExportAuthority,
)


def test_formal_editable_pptx_authority_is_render_scene() -> None:
    assert FORMAL_EDITABLE_PPTX_AUTHORITY is FormalExportAuthority.RENDER_SCENE
    assert RENDER_EDIT_AUTHORITY == "render_scene"
    assert CONTENT_EXPRESSION_AUTHORITY == "slide_spec"
    assert GEOMETRY_COMPILE_AUTHORITY == "layout_plan"
    assert LEGACY_TEMPLATE_EXPORT_KIND == DerivedExportKind.PRESENTATION_SPEC.value


def test_presentation_spec_module_marks_legacy_derived() -> None:
    module_doc = presentation_spec_module.__doc__ or ""
    assert "DOM-003" in module_doc
    assert "derived" in module_doc.lower()
    class_doc = presentation_spec_module.PresentationSpec.__doc__ or ""
    assert "legacy" in class_doc.lower() or "derived" in class_doc.lower()
