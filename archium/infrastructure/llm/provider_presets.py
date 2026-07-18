"""Built-in LLM provider presets for the settings UI."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderPreset:
    slug: str
    label: str
    base_url: str
    model: str


PROVIDER_PRESETS: tuple[ProviderPreset, ...] = (
    ProviderPreset(
        slug="gemini",
        label="Gemini",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        model="gemini-2.5-flash",
    ),
    ProviderPreset(
        slug="openai",
        label="OpenAI",
        base_url="https://api.openai.com/v1",
        model="gpt-4o-mini",
    ),
    ProviderPreset(
        slug="deepseek",
        label="DeepSeek",
        base_url="https://api.deepseek.com/v1",
        model="deepseek-chat",
    ),
    ProviderPreset(
        slug="openrouter",
        label="OpenRouter",
        base_url="https://openrouter.ai/api/v1",
        model="google/gemini-2.5-flash",
    ),
    ProviderPreset(
        slug="custom",
        label="自定义 OpenAI-Compatible",
        base_url="",
        model="",
    ),
)

PROVIDER_LABELS: tuple[str, ...] = tuple(p.label for p in PROVIDER_PRESETS)
PROVIDER_BY_LABEL: dict[str, ProviderPreset] = {p.label: p for p in PROVIDER_PRESETS}
PROVIDER_BY_SLUG: dict[str, ProviderPreset] = {p.slug: p for p in PROVIDER_PRESETS}


def label_for_slug(slug: str) -> str:
    preset = PROVIDER_BY_SLUG.get(slug)
    return preset.label if preset else PROVIDER_PRESETS[-1].label


def slug_for_label(label: str) -> str:
    preset = PROVIDER_BY_LABEL.get(label)
    return preset.slug if preset else "custom"
