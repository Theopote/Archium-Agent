"""UI-specific services."""

from __future__ import annotations

from typing import Any

__all__ = [
    "WorkspaceModeService",
    "ProductContinueWork",
    "ProductStageTruth",
]

_LAZY_ATTRS: dict[str, tuple[str, str]] = {
    "WorkspaceModeService": ("archium.application.ui.workspace_mode_service", "WorkspaceModeService"),
    "ProductContinueWork": ("archium.application.ui.product_continue_work", "ProductContinueWork"),
    "ProductStageTruth": ("archium.application.ui.product_stage_truth", "ProductStageTruth"),
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
