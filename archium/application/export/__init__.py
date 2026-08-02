"""Export and rendering services."""

from __future__ import annotations

from typing import Any

__all__ = [
    "ExportService",
    "ExportPolicyService",
    "ExportRoundTripService",
    "FormalPPTXExportService",
    "RenderExport",
]

_LAZY_ATTRS: dict[str, tuple[str, str]] = {
    "ExportService": ("archium.application.export.export_service", "ExportService"),
    "ExportPolicyService": ("archium.application.export.export_policy_service", "ExportPolicyService"),
    "ExportRoundTripService": ("archium.application.export.export_round_trip_service", "ExportRoundTripService"),
    "FormalPPTXExportService": ("archium.application.export.formal_pptx_export_service", "FormalPPTXExportService"),
    "RenderExport": ("archium.application.export.render_export", "RenderExport"),
}

def __getattr__(name: str) -> Any:
    target = _LAZY_ATTRS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr = target
    from importlib import import_module
    
    value = getattr(import_module(module_name), attr)
    globals()[name] = value
    return value
