"""AI service settings page."""

from __future__ import annotations

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
                        session_store=st.session_state,
                    )
                session.commit()
            reset_llm_provider_cache()
            st.success("AI 配置已保存")
            st.rerun()

    if delete_clicked:
        with get_session() as session:
            delete_service = LLMProfileService(session)
            delete_service.delete_api_key(draft_profile, session_store=st.session_state)
            session.commit()
        reset_llm_provider_cache()
        st.warning("已删除本机凭据库中的 API Key（环境变量不受影响）")
        st.rerun()

    effective = get_ui_effective_settings()
    if effective.llm_configured:
        st.info("当前 Archium 已具备 LLM 调用能力，可在项目工作台开始生成。")
    else:
        st.warning("尚未配置可用的 LLM API Key。可在此页面配置，或在 `.env` 中设置 `GEMINI_API_KEY`。")
