"""LLM-related services."""

from __future__ import annotations

from typing import Any

__all__ = [
    "LLMProfileService",
    "LLMSettingsResolver",
    "ModelRoleRouter",
]

_LAZY_ATTRS: dict[str, tuple[str, str]] = {
    "LLMProfileService": ("archium.application.llm.llm_profile_service", "LLMProfileService"),
    "LLMSettingsResolver": ("archium.application.llm.llm_settings_resolver", "LLMSettingsResolver"),
    "ModelRoleRouter": ("archium.application.llm.model_role_router", "ModelRoleRouter"),
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
