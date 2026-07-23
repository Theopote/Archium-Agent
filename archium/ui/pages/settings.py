"""AI service settings page."""

from __future__ import annotations

from typing import cast

import streamlit as st

from archium.application.llm_profile_service import CredentialStatus, LLMProfileService
from archium.config import get_settings
from archium.domain.llm_profile import LLMProfile
from archium.infrastructure.database.session import get_session
from archium.infrastructure.llm.connection_test import verify_llm_connection
from archium.infrastructure.llm.factory import reset_llm_provider_cache
from archium.infrastructure.llm.provider_presets import (
    PROVIDER_BY_SLUG,
    PROVIDER_LABELS,
    label_for_slug,
    slug_for_label,
)
from archium.ui.llm_settings import get_ui_effective_settings

_SOURCE_LABELS = {
    "session": "本次会话",
    "keyring": "本机安全凭据库",
    "env": "环境变量 / .env",
    "none": "未配置",
}


def _load_profile_and_status() -> tuple[LLMProfile, CredentialStatus]:
    base_settings = get_settings()
    with get_session() as session:
        service = LLMProfileService(session)
        profile = service.get_or_create_default_profile()
        status = service.credential_status(
            profile,
            session_api_key=st.session_state.get("llm_session_api_key"),
            env_api_key=base_settings.llm_api_key,
        )
    return profile, status


def _resolve_api_key_for_action(
    profile: LLMProfile,
    *,
    typed_key: str,
) -> str | None:
    if typed_key.strip():
        return typed_key.strip()
    with get_session() as session:
        service = LLMProfileService(session)
        session_key = st.session_state.get("llm_session_api_key")
        api_key, _ = service.resolve_api_key(
            profile,
            session_api_key=session_key if isinstance(session_key, str) else None,
            env_api_key=get_settings().llm_api_key,
        )
        return api_key


def render() -> None:
    st.markdown("### AI 服务")
    st.caption("配置 LLM 服务商、API Key 与模型。密钥优先保存在本机操作系统凭据库，不会写入项目数据库。")

    profile, credential_status = _load_profile_and_status()

    provider_label = label_for_slug(profile.provider)
    default_index = PROVIDER_LABELS.index(provider_label) if provider_label in PROVIDER_LABELS else 0

    selected_label = st.selectbox("AI 服务商", PROVIDER_LABELS, index=default_index)
    selected_slug = slug_for_label(selected_label)
    preset = PROVIDER_BY_SLUG[selected_slug]

    if credential_status.configured and credential_status.masked_hint:
        key_placeholder = f"已配置：{credential_status.masked_hint}"
    else:
        key_placeholder = "输入 API Key"

    api_key_input = st.text_input(
        "API Key",
        type="password",
        placeholder=key_placeholder,
        help="留空则沿用已保存的密钥；输入新值将覆盖测试/保存时使用的 Key。",
    )

    base_url_default = profile.base_url if profile.provider == selected_slug else preset.base_url
    model_default = profile.model if profile.provider == selected_slug else preset.model

    base_url = st.text_input("Base URL", value=base_url_default or preset.base_url)
    model = st.text_input("模型", value=model_default or preset.model)
    temperature = st.slider("Temperature", min_value=0.0, max_value=2.0, value=float(profile.temperature), step=0.1)
    timeout_seconds = st.number_input(
        "请求超时（秒）",
        min_value=5.0,
        max_value=600.0,
        value=float(profile.timeout_seconds),
        step=5.0,
    )

    save_mode = st.radio(
        "密钥保存方式",
        ["保存到本机安全凭据库", "仅本次会话"],
        horizontal=True,
    )

    st.markdown(
        f"**当前密钥来源：** {_SOURCE_LABELS[credential_status.source]}"
        + (f"（{credential_status.masked_hint}）" if credential_status.masked_hint else "")
    )

    test_col, save_col, delete_col = st.columns(3)
    test_clicked = test_col.button("测试连接", type="secondary", use_container_width=True)
    save_clicked = save_col.button("保存配置", type="primary", use_container_width=True)
    delete_clicked = delete_col.button("删除密钥", use_container_width=True)

    draft_profile = profile.model_copy(
        update={
            "provider": selected_slug,
            "base_url": base_url.strip() or None,
            "model": model.strip(),
            "temperature": temperature,
            "timeout_seconds": timeout_seconds,
        }
    )

    if test_clicked:
        api_key = _resolve_api_key_for_action(draft_profile, typed_key=api_key_input)
        if not api_key:
            st.error("请先输入 API Key，或保存一个有效密钥后再测试。")
        elif not draft_profile.model.strip():
            st.error("请填写模型名称。")
        else:
            with st.spinner("正在测试连接…"):
                result = verify_llm_connection(
                    api_key=api_key,
                    base_url=draft_profile.base_url,
                    model=draft_profile.model.strip(),
                    timeout_seconds=min(float(timeout_seconds), 30.0),
                )
            if result.success:
                st.success(
                    f"连接成功\n\n"
                    f"模型：{result.model}\n\n"
                    f"响应时间：{result.latency_ms / 1000:.1f} 秒"
                )
            else:
                st.error(result.message)

    if save_clicked:
        if not draft_profile.model.strip():
            st.error("请填写模型名称。")
        elif not api_key_input.strip() and not credential_status.configured:
            st.error("首次保存需要输入 API Key。")
        else:
            with get_session() as session:
                save_service = LLMProfileService(session)
                save_service.save_default_profile(draft_profile)
                if api_key_input.strip():
                    save_service.save_api_key(
                        draft_profile,
                        api_key_input.strip(),
                        persist=save_mode == "保存到本机安全凭据库",
                        session_store=cast(dict[str, object], st.session_state),
                    )
            reset_llm_provider_cache()
            st.success("AI 配置已保存")
            st.rerun()

    if delete_clicked:
        with get_session() as session:
            delete_service = LLMProfileService(session)
            delete_service.delete_api_key(
                draft_profile, session_store=cast(dict[str, object], st.session_state)
            )
        reset_llm_provider_cache()
        st.warning("已删除本机凭据库中的 API Key（环境变量不受影响）")
        st.rerun()

    effective = get_ui_effective_settings()
    if effective.llm_configured:
        st.info("当前 Archium 已具备 LLM 调用能力，可在「制作」五阶段开始生成。")
    else:
        st.warning("尚未配置可用的 LLM API Key。可在此页面配置，或在 `.env` 中设置 `GEMINI_API_KEY`。")

    st.divider()
    _render_model_role_mapping(draft_profile)
    st.divider()
    _render_system_diagnostics()
    st.divider()
    _render_about()
    st.divider()
    _render_image_search_settings()


def _render_model_role_mapping(draft_profile: LLMProfile) -> None:
    from archium.application.model_role_router import ModelRoleRegistryService
    from archium.domain.model_roles import (
        CORE_MODEL_ROLES,
        ModelRole,
        ModelRoleAssignment,
        model_profile_from_llm_profile,
    )

    st.markdown("### 高级：模型角色映射")
    st.caption(
        "日常生成使用上方默认 LLM 配置。"
        "可选角色（OCR、图像生成等）未配置时不影响普通生成流程。"
    )

    with get_session() as session:
        registry = ModelRoleRegistryService(session)
        profiles = registry.list_profiles()
        assignments = registry.list_role_assignments()

    if not profiles:
        profiles = [
            model_profile_from_llm_profile(
                profile_id="default",
                provider=draft_profile.provider,
                model=draft_profile.model,
                base_url=draft_profile.base_url,
                timeout_seconds=draft_profile.timeout_seconds,
            )
        ]

    profile_labels = {p.id: f"{p.id} · {p.provider}/{p.model}" for p in profiles}
    assignment_by_role = {a.role: a.profile_id for a in assignments}

    with st.expander("角色 → 模型配置", expanded=False):
        new_assignments: list[ModelRoleAssignment] = []
        for role in ModelRole:
            optional = role not in CORE_MODEL_ROLES
            label = f"{role.value}" + ("（可选）" if optional else "")
            options = ["（未指定）"] + list(profile_labels.keys())
            current = assignment_by_role.get(role)
            index = options.index(current) if current in options else 0
            picked = st.selectbox(
                label,
                options=options,
                index=index,
                format_func=lambda value: profile_labels.get(value, value),
                key=f"model_role_map_{role.value}",
            )
            if picked != "（未指定）":
                new_assignments.append(ModelRoleAssignment(role=role, profile_id=picked))

        if st.button("保存角色映射", key="save_model_role_mapping"):
            with get_session() as session:
                save_registry = ModelRoleRegistryService(session)
                save_registry.save_profiles(profiles)
                save_registry.save_role_assignments(new_assignments)
            st.success("模型角色映射已保存")
            st.rerun()

        configured = {a.role for a in new_assignments} | {
            role for profile in profiles for role in profile.roles
        }
        missing_optional = [r for r in ModelRole if r not in CORE_MODEL_ROLES and r not in configured]
        if missing_optional:
            st.caption(
                "未配置的可选角色："
                + "、".join(r.value for r in missing_optional)
                + "。调用这些能力前需在此指定模型。"
            )


def _render_system_diagnostics() -> None:
    from archium.ui.system_diagnostics import render_system_diagnostics

    st.markdown("### 系统诊断")
    st.caption("运行依赖与导出工具状态。日常进度请看侧栏「当前项目」。")
    render_system_diagnostics()


def _render_about() -> None:
    from archium.ui.branding import render_about_panel

    render_about_panel()


def _render_image_search_settings() -> None:
    from archium.application.image_search_settings_service import ImageSearchSettingsService
    from archium.config.settings import get_settings
    from archium.infrastructure.database.session import get_session
    from archium.ui.image_search_settings import (
        delete_pexels_api_key,
        delete_unsplash_api_key,
        pexels_credential_status,
        save_pexels_api_key,
        save_unsplash_api_key,
        unsplash_credential_status,
    )

    st.markdown("### 网络搜图")
    st.caption(
        "导出 PPTX 时，若项目素材缺失，可为效果图/现场照片/参考案例页自动检索授权图。"
        "不会用于总平、平面图等需精确标注的图纸类型。"
    )

    base_settings = get_settings()
    with get_session() as session:
        prefs_service = ImageSearchSettingsService(session)
        prefs = prefs_service.get_preferences(base_settings=base_settings)

    enabled = st.toggle("启用网络搜图", value=prefs.enabled)
    persist_to_library = st.toggle(
        "保存到项目素材库",
        value=prefs.persist_to_library,
        help="下载的授权图会复制到项目 web_imports 目录，便于后续复用与手动分配。",
    )

    st.markdown("#### Pexels")
    pexels_configured, pexels_masked, pexels_source = pexels_credential_status()
    pexels_key_input = st.text_input(
        "Pexels API Key",
        type="password",
        placeholder=f"已配置：{pexels_masked}" if pexels_masked else "输入 Pexels API Key",
        help="在 https://www.pexels.com/api/ 申请。",
        key="pexels_api_key_input",
    )
    pexels_save_mode = st.radio(
        "Pexels 密钥保存方式",
        ["保存到本机安全凭据库", "仅本次会话"],
        horizontal=True,
        key="pexels_save_mode",
    )
    st.caption(
        f"Pexels 密钥来源：{_SOURCE_LABELS[pexels_source]}"
        + (f"（{pexels_masked}）" if pexels_masked else "")
    )

    st.markdown("#### Unsplash（备选）")
    unsplash_configured, unsplash_masked, unsplash_source = unsplash_credential_status()
    unsplash_key_input = st.text_input(
        "Unsplash Access Key",
        type="password",
        placeholder=f"已配置：{unsplash_masked}" if unsplash_masked else "输入 Unsplash Access Key",
        help="在 https://unsplash.com/developers 申请。Pexels 无结果时会尝试 Unsplash。",
        key="unsplash_api_key_input",
    )
    unsplash_save_mode = st.radio(
        "Unsplash 密钥保存方式",
        ["保存到本机安全凭据库", "仅本次会话"],
        horizontal=True,
        key="unsplash_save_mode",
    )
    st.caption(
        f"Unsplash 密钥来源：{_SOURCE_LABELS[unsplash_source]}"
        + (f"（{unsplash_masked}）" if unsplash_masked else "")
    )

    save_col, delete_pexels_col, delete_unsplash_col = st.columns(3)
    save_clicked = save_col.button("保存搜图配置", type="primary", use_container_width=True)
    delete_pexels_clicked = delete_pexels_col.button("删除 Pexels 密钥", use_container_width=True)
    delete_unsplash_clicked = delete_unsplash_col.button("删除 Unsplash 密钥", use_container_width=True)

    if save_clicked:
        if not pexels_configured and not unsplash_configured and not pexels_key_input.strip() and not unsplash_key_input.strip():
            st.error("请至少配置 Pexels 或 Unsplash 其中一个 API Key。")
        else:
            with get_session() as session:
                ImageSearchSettingsService(session).save_preferences(
                    enabled=enabled,
                    persist_to_library=persist_to_library,
                )
            if pexels_key_input.strip():
                save_pexels_api_key(
                    api_key=pexels_key_input.strip(),
                    persist=pexels_save_mode == "保存到本机安全凭据库",
                    session_store=cast(dict[str, object], st.session_state),
                )
            if unsplash_key_input.strip():
                save_unsplash_api_key(
                    api_key=unsplash_key_input.strip(),
                    persist=unsplash_save_mode == "保存到本机安全凭据库",
                    session_store=cast(dict[str, object], st.session_state),
                )
            st.success("搜图配置已保存")
            st.rerun()

    if delete_pexels_clicked:
        delete_pexels_api_key(session_store=cast(dict[str, object], st.session_state))
        st.warning("已删除 Pexels API Key")
        st.rerun()

    if delete_unsplash_clicked:
        delete_unsplash_api_key(session_store=cast(dict[str, object], st.session_state))
        st.warning("已删除 Unsplash Access Key")
        st.rerun()

    if pexels_configured or unsplash_configured:
        providers = []
        if pexels_configured:
            providers.append("Pexels")
        if unsplash_configured:
            providers.append("Unsplash")
        st.info(f"已配置 {' / '.join(providers)}，导出时将按顺序尝试检索授权配图。")
    else:
        st.warning("尚未配置搜图 API Key。可在此页面配置，或在 `.env` 中设置 `PEXELS_API_KEY` / `UNSPLASH_ACCESS_KEY`。")

    st.divider()
    with st.expander("开发者与验收", expanded=False):
        st.caption("Benchmark 与视觉语料用于产品研发验收，不属于日常项目交付。")
        from archium.ui.benchmark_review_panel import render_benchmark_review_panel
        from archium.ui.visual_qa_corpus_panel import render_visual_qa_corpus_panel

        render_benchmark_review_panel()
        st.divider()
        render_visual_qa_corpus_panel()
