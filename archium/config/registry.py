"""Configuration registry — single source of truth for settings metadata and doc generation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import AliasChoices
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined

from archium.config.settings import Settings

_GENERATED_HEADER = (
    "# AUTO-GENERATED from archium/config/settings.py — do not edit manually.\n"
    "# Regenerate: python scripts/generate_config_docs.py\n"
    "# Copy to .env and fill in values as needed.\n"
    "# The app starts without an API key; LLM features require configuration.\n"
    "# Never commit a filled .env — Archium is MIT-licensed; secrets remain your responsibility.\n"
)


class ConfigDomain(StrEnum):
    APP = "app"
    STORAGE = "storage"
    LLM = "llm"
    EMBEDDING = "embedding"
    RETRIEVAL = "retrieval"
    CHUNKING = "chunking"
    WORKFLOW = "workflow"
    REVIEW = "review"
    REPAIR = "repair"
    RENDER = "render"
    VISUAL = "visual"
    LEGACY = "legacy"


DOMAIN_LABELS: dict[ConfigDomain, str] = {
    ConfigDomain.APP: "Application",
    ConfigDomain.STORAGE: "Storage paths",
    ConfigDomain.LLM: "LLM (OpenAI-compatible)",
    ConfigDomain.EMBEDDING: "Embedding",
    ConfigDomain.RETRIEVAL: "retrieval.* — Vector retrieval (Chroma)",
    ConfigDomain.CHUNKING: "Document chunking",
    ConfigDomain.WORKFLOW: "Workflow",
    ConfigDomain.REVIEW: "review.* — Quality review & export gating",
    ConfigDomain.REPAIR: "repair.* — Automated slide repair",
    ConfigDomain.RENDER: "render.* — Marp & PptxGenJS export",
    ConfigDomain.VISUAL: "Visual fallback, layout thresholds & web image search",
    ConfigDomain.LEGACY: "Legacy modules (optional)",
}

DOMAIN_ORDER: tuple[ConfigDomain, ...] = tuple(ConfigDomain)

FIELD_DOMAINS: dict[str, ConfigDomain] = {
    "app_name": ConfigDomain.APP,
    "environment": ConfigDomain.APP,
    "log_level": ConfigDomain.APP,
    "database_path": ConfigDomain.STORAGE,
    "database_url": ConfigDomain.STORAGE,
    "database_pool_size": ConfigDomain.STORAGE,
    "database_max_overflow": ConfigDomain.STORAGE,
    "database_pool_recycle_seconds": ConfigDomain.STORAGE,
    "database_pool_pre_ping": ConfigDomain.STORAGE,
    "database_sqlite_busy_timeout_ms": ConfigDomain.STORAGE,
    "database_sqlite_wal_enabled": ConfigDomain.STORAGE,
    "workflow_checkpoint_path": ConfigDomain.STORAGE,
    "workflow_checkpoint_commit_enabled": ConfigDomain.STORAGE,
    "streamlit_background_workflows_enabled": ConfigDomain.APP,
    "project_storage_path": ConfigDomain.STORAGE,
    "output_path": ConfigDomain.STORAGE,
    "chroma_path": ConfigDomain.STORAGE,
    "chroma_max_documents": ConfigDomain.STORAGE,
    "workflow_checkpoint_retention_days": ConfigDomain.STORAGE,
    "llm_provider": ConfigDomain.LLM,
    "llm_api_key": ConfigDomain.LLM,
    "llm_base_url": ConfigDomain.LLM,
    "llm_model": ConfigDomain.LLM,
    "llm_max_retries": ConfigDomain.LLM,
    "llm_max_concurrent_requests": ConfigDomain.LLM,
    "llm_repair_attempts": ConfigDomain.LLM,
    "llm_timeout_seconds": ConfigDomain.LLM,
    "embedding_provider": ConfigDomain.EMBEDDING,
    "embedding_api_key": ConfigDomain.EMBEDDING,
    "embedding_base_url": ConfigDomain.EMBEDDING,
    "embedding_model": ConfigDomain.EMBEDDING,
    "embedding_dimensions": ConfigDomain.EMBEDDING,
    "retrieval_enabled": ConfigDomain.RETRIEVAL,
    "retrieval_top_k": ConfigDomain.RETRIEVAL,
    "asset_vision_rag_enabled": ConfigDomain.RETRIEVAL,
    "asset_vision_llm_enabled": ConfigDomain.RETRIEVAL,
    "asset_vision_llm_model": ConfigDomain.RETRIEVAL,
    "retrieval_keyword_boost_enabled": ConfigDomain.RETRIEVAL,
    "chunk_context_max_chars": ConfigDomain.RETRIEVAL,
    "embedding_chunking_enabled": ConfigDomain.CHUNKING,
    "embedding_chunk_min_segment_chars": ConfigDomain.CHUNKING,
    "embedding_breakpoint_threshold": ConfigDomain.CHUNKING,
    "semantic_chunking_enabled": ConfigDomain.CHUNKING,
    "chunk_max_chars": ConfigDomain.CHUNKING,
    "chunk_min_chars": ConfigDomain.CHUNKING,
    "chunk_overlap_chars": ConfigDomain.CHUNKING,
    "fact_extraction_enabled": ConfigDomain.WORKFLOW,
    "block_export_on_critical_review": ConfigDomain.REVIEW,
    "llm_professional_review_enabled": ConfigDomain.REVIEW,
    "visual_qa_enabled": ConfigDomain.REVIEW,
    "visual_critic_enabled": ConfigDomain.REVIEW,
    "visual_deck_qa_enabled": ConfigDomain.REVIEW,
    "visual_critic_llm_enabled": ConfigDomain.REVIEW,
    "visual_critic_llm_model": ConfigDomain.REVIEW,
    "visual_pptx_screenshots_enabled": ConfigDomain.REVIEW,
    "induction_screenshot_clustering_enabled": ConfigDomain.REVIEW,
    "induction_screenshot_clustering_weight": ConfigDomain.REVIEW,
    "slide_per_page_generation": ConfigDomain.LLM,
    "slide_repair_enabled": ConfigDomain.REPAIR,
    "slide_repair_max_rounds": ConfigDomain.REPAIR,
    "scene_repair_enabled": ConfigDomain.REPAIR,
    "scene_repair_max_rounds": ConfigDomain.REPAIR,
    "marp_command": ConfigDomain.RENDER,
    "marp_preview_images_enabled": ConfigDomain.RENDER,
    "marp_preview_image_format": ConfigDomain.RENDER,
    "pptxgen_node_command": ConfigDomain.RENDER,
    "pptxgen_script_path": ConfigDomain.RENDER,
    "visual_fallback_enabled": ConfigDomain.VISUAL,
    "visual_fallback_relaxed_matching": ConfigDomain.VISUAL,
    "visual_fallback_relaxed_min_score": ConfigDomain.VISUAL,
    "visual_fallback_generate_diagrams": ConfigDomain.VISUAL,
    "layout_min_body_font_pt": ConfigDomain.VISUAL,
    "layout_min_caption_font_pt": ConfigDomain.VISUAL,
    "layout_min_source_font_pt": ConfigDomain.VISUAL,
    "layout_min_hero_area_ratio": ConfigDomain.VISUAL,
    "layout_min_whitespace_ratio": ConfigDomain.VISUAL,
    "layout_max_whitespace_ratio": ConfigDomain.VISUAL,
    "web_image_search_enabled": ConfigDomain.VISUAL,
    "web_image_search_provider": ConfigDomain.VISUAL,
    "pexels_api_key": ConfigDomain.VISUAL,
    "web_image_search_timeout_seconds": ConfigDomain.VISUAL,
    "web_image_search_per_page": ConfigDomain.VISUAL,
    "web_image_search_persist_to_library": ConfigDomain.VISUAL,
    "unsplash_access_key": ConfigDomain.VISUAL,
}


@dataclass(frozen=True, slots=True)
class SettingSpec:
    field_name: str
    domain: ConfigDomain
    env_vars: tuple[str, ...]
    default: Any
    default_display: str
    description: str
    required_for_startup: bool


def _env_var_names(field_name: str, field_info: FieldInfo) -> tuple[str, ...]:
    alias = field_info.validation_alias
    if isinstance(alias, AliasChoices):
        return tuple(str(choice) for choice in alias.choices)
    if isinstance(alias, str):
        return (alias,)
    return (field_name.upper(),)


def _format_default(value: Any) -> str:
    if value is None or value is PydanticUndefined:
        return "—"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, Path):
        return value.as_posix()
    return str(value)


def _is_required_for_startup(field_name: str, default: Any) -> bool:
    if field_name.endswith("_api_key") or field_name.endswith("_access_key"):
        return False
    if field_name.endswith("_token") or field_name.endswith("_user_id"):
        return False
    if default is None or default is PydanticUndefined:
        return False
    return False


def iter_setting_specs() -> list[SettingSpec]:
    specs: list[SettingSpec] = []
    for field_name, field_info in Settings.model_fields.items():
        domain = FIELD_DOMAINS.get(field_name)
        if domain is None:
            msg = f"Missing domain mapping for Settings field: {field_name}"
            raise ValueError(msg)
        default = field_info.default
        specs.append(
            SettingSpec(
                field_name=field_name,
                domain=domain,
                env_vars=_env_var_names(field_name, field_info),
                default=default,
                default_display=_format_default(default),
                description=field_info.description or "",
                required_for_startup=_is_required_for_startup(field_name, default),
            )
        )
    return specs


def _group_specs_by_domain(specs: list[SettingSpec]) -> dict[ConfigDomain, list[SettingSpec]]:
    grouped: dict[ConfigDomain, list[SettingSpec]] = {domain: [] for domain in DOMAIN_ORDER}
    for spec in specs:
        grouped[spec.domain].append(spec)
    return grouped


def render_env_example() -> str:
    lines = [
        _GENERATED_HEADER.rstrip("\n"),
        "",
    ]
    grouped = _group_specs_by_domain(iter_setting_specs())
    for domain in DOMAIN_ORDER:
        domain_specs = grouped[domain]
        if not domain_specs:
            continue
        lines.append(f"# ── {DOMAIN_LABELS[domain]} ──")
        for spec in domain_specs:
            primary_env = spec.env_vars[0]
            if spec.default is None or spec.default is PydanticUndefined:
                comment = f"# {primary_env}="
            else:
                comment = f"# {primary_env}={spec.default_display}"
            if spec.description:
                comment = f"{comment}  # {spec.description}"
            if len(spec.env_vars) > 1:
                aliases = " / ".join(spec.env_vars[1:])
                comment = f"{comment} (aliases: {aliases})"
            lines.append(comment)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_markdown_reference() -> str:
    lines = [
        "<!-- AUTO-GENERATED from archium/config/settings.py — do not edit manually. -->",
        "<!-- Regenerate: python scripts/generate_config_docs.py -->",
        "",
        "# Configuration Reference",
        "",
        "Single source of truth: [`archium/config/settings.py`](../archium/config/settings.py).",
        "",
        "This file and [`.env.example`](../.env.example) are generated and checked in CI.",
        "Do not edit them manually.",
        "",
        "> The app starts without an API Key. LLM-dependent features fail at runtime with a clear error.",
        "",
    ]
    grouped = _group_specs_by_domain(iter_setting_specs())
    for domain in DOMAIN_ORDER:
        domain_specs = grouped[domain]
        if not domain_specs:
            continue
        anchor = domain.value
        lines.append(f"## {DOMAIN_LABELS[domain]} {{#{anchor}}}")
        lines.append("")
        lines.append("| Environment variable | Default | Required at startup | Description |")
        lines.append("|----------------------|---------|:-------------------:|-------------|")
        for spec in domain_specs:
            env_display = " / ".join(f"`{name}`" for name in spec.env_vars)
            default = spec.default_display if spec.default_display != "—" else "*(unset)*"
            required = "Yes" if spec.required_for_startup else "No"
            description = spec.description.replace("|", "\\|") if spec.description else "—"
            lines.append(f"| {env_display} | `{default}` | {required} | {description} |")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def validate_registry() -> None:
    """Ensure every Settings field has a domain mapping and vice versa."""
    model_fields = set(Settings.model_fields)
    mapped_fields = set(FIELD_DOMAINS)
    missing = model_fields - mapped_fields
    extra = mapped_fields - model_fields
    if missing:
        raise ValueError(f"Settings fields missing from FIELD_DOMAINS: {sorted(missing)}")
    if extra:
        raise ValueError(f"FIELD_DOMAINS entries not in Settings: {sorted(extra)}")
