"""Built-in LLM provider presets for the settings UI."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderPreset:
    slug: str
    label: str
    base_url: str
    model: str
    models: tuple[str, ...] = ()


PROVIDER_PRESETS: tuple[ProviderPreset, ...] = (
    ProviderPreset(
        slug="gemini",
        label="Gemini",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        model="gemini-2.5-flash",
        models=(
            "gemini-2.5-flash",
            "gemini-2.5-pro",
            "gemini-2.0-flash",
        ),
    ),
    ProviderPreset(
        slug="openai",
        label="OpenAI",
        base_url="https://api.openai.com/v1",
        model="gpt-4o-mini",
        models=(
            "gpt-4o-mini",
            "gpt-4o",
            "gpt-4.1-mini",
            "gpt-4.1",
            "o4-mini",
        ),
    ),
    ProviderPreset(
        slug="deepseek",
        label="DeepSeek",
        base_url="https://api.deepseek.com/v1",
        model="deepseek-v4-flash",
        models=(
            "deepseek-v4-flash",
            "deepseek-v4-pro",
        ),
    ),
    ProviderPreset(
        slug="openrouter",
        label="OpenRouter",
        base_url="https://openrouter.ai/api/v1",
        model="google/gemini-2.5-flash",
        models=(
            "google/gemini-2.5-flash",
            "google/gemini-2.5-pro",
            "openai/gpt-4o-mini",
            "openai/gpt-4o",
            "deepseek/deepseek-chat",
            "anthropic/claude-sonnet-4",
        ),
    ),
    ProviderPreset(
        slug="custom",
        label="自定义 OpenAI-Compatible",
        base_url="",
        model="",
        models=(),
    ),
)

PROVIDER_LABELS: tuple[str, ...] = tuple(p.label for p in PROVIDER_PRESETS)
PROVIDER_BY_LABEL: dict[str, ProviderPreset] = {p.label: p for p in PROVIDER_PRESETS}
PROVIDER_BY_SLUG: dict[str, ProviderPreset] = {p.slug: p for p in PROVIDER_PRESETS}

CUSTOM_MODEL_OPTION = "自定义…"


def label_for_slug(slug: str) -> str:
    preset = PROVIDER_BY_SLUG.get(slug)
    return preset.label if preset else PROVIDER_PRESETS[-1].label


def slug_for_label(label: str) -> str:
    preset = PROVIDER_BY_LABEL.get(label)
    return preset.slug if preset else "custom"


def recommended_models_for_slug(slug: str) -> tuple[str, ...]:
    """Ordered model choices for the settings dropdown (default first)."""
    preset = PROVIDER_BY_SLUG.get(slug)
    if preset is None:
        return ()
    ordered: list[str] = []
    if preset.model.strip():
        ordered.append(preset.model.strip())
    for item in preset.models:
        name = item.strip()
        if name and name not in ordered:
            ordered.append(name)
    return tuple(ordered)
