"""Slide Recovery result panel — previews, metrics, fidelity, and delivery."""

from __future__ import annotations

import contextlib
from uuid import UUID

import streamlit as st

from archium.application.slide_recovery_delivery_service import SlideRecoveryDeliveryService
from archium.application.slide_recovery_workflow_service import SlideRecoveryWorkflowResult
from archium.config.settings import Settings
from archium.domain.enums import WorkflowStatus
from archium.domain.export_fidelity import FIDELITY_LABELS_ZH
from archium.domain.slide_recovery import PAGE_KIND_LABELS_ZH, HybridRenderScene
from archium.exceptions import WorkflowError
from archium.infrastructure.database.session import get_session
from archium.ui.delivery.export_policy_panel import EXPORT_POLICY_PRESETS
from archium.ui.error_handlers import format_user_error
from archium.ui.slide_recovery_region_panel import render_slide_recovery_region_editor


def render_slide_recovery_result_panel(
    result: SlideRecoveryWorkflowResult | None,
    *,
    project_id: UUID | None = None,
    settings: Settings | None = None,
    key_prefix: str = "slide_recovery",
) -> SlideRecoveryWorkflowResult | None:
    if result is None:
        return None

    recovery = result.recovery_result
    hybrid = result.hybrid_scene or (recovery.hybrid_scene if recovery else None)
    if recovery is None and hybrid is None:
        st.info("恢复结果尚未生成。")
        return None

    st.markdown("#### 恢复结果")
    if hybrid is not None:
        st.caption(
            f"页面类型：{PAGE_KIND_LABELS_ZH.get(hybrid.page_kind, hybrid.page_kind.value)} · "
            f"可编辑级别：{hybrid.fidelity_label_zh()}"
        )

    _render_preview_row(result, project_id=project_id, settings=settings)

    updated_result: SlideRecoveryWorkflowResult | None = None
    if project_id is not None and settings is not None:
        updated_result = render_slide_recovery_region_editor(
            result,
            project_id=project_id,
            settings=settings,
            key_prefix=f"{key_prefix}_region",
        )
    if updated_result is not None:
        return updated_result

    if recovery is not None:
        for line in recovery.summary_lines_zh():
            st.write(line)
        meta = recovery.analysis_meta or {}
        if meta:
            ocr_engine = meta.get("ocr_engine")
            vlm_source = meta.get("vlm_source")
            mode = meta.get("analysis_mode")
            parts: list[str] = []
            if mode:
                parts.append(f"分析模式：{mode}")
            if ocr_engine:
                parts.append(f"OCR：{ocr_engine}")
            if vlm_source:
                parts.append(f"VLM：{vlm_source}")
            if parts:
                st.caption(" · ".join(parts))

    metrics = recovery.metrics if recovery is not None else hybrid.metrics if hybrid else None
    if metrics is not None:
        cols = st.columns(3)
        cols[0].metric("文本召回率", f"{metrics.text_recall:.0%}")
        cols[1].metric("位置误差", f"{metrics.text_position_error:.1%}")
        cols[2].metric("视觉相似度", f"{metrics.similarity_score:.0%}")

        with st.expander("完整指标", expanded=False):
            for line in metrics.summary_lines_zh():
                st.write(line)

    fidelity = (
        recovery.reconstruction_fidelity
        if recovery is not None
        else hybrid.reconstruction_fidelity if hybrid else None
    )
    if fidelity is not None:
        st.caption(f"导出保真度：{FIDELITY_LABELS_ZH.get(fidelity, fidelity.value)}")

    warnings = list(result.warnings)
    if recovery is not None:
        warnings.extend(recovery.warnings)
    if warnings:
        st.warning("；".join(warnings))

    if result.errors:
        st.error("；".join(result.errors))

    if hybrid is not None and hybrid.hybrid_bitmap_region_ids:
        st.caption(
            f"混合 Bitmap 区域：{len(hybrid.hybrid_bitmap_region_ids)} 个 "
            "（复杂视觉保持为图片对象）"
        )

    if hybrid is not None and hybrid.scene.nodes:
        with st.expander("Hybrid RenderScene 节点", expanded=False):
            for node in hybrid.scene.sorted_nodes():
                st.write(f"- `{node.id}` · {node.node_type} · {node.semantic_role or '—'}")

    if project_id is not None and settings is not None and hybrid is not None:
        _render_delivery_actions(
            result,
            project_id=project_id,
            settings=settings,
            key_prefix=key_prefix,
        )

    return None


def _render_preview_row(
    result: SlideRecoveryWorkflowResult,
    *,
    project_id: UUID | None,
    settings: Settings | None,
) -> None:
    if project_id is None or settings is None:
        return
    hybrid = result.hybrid_scene or (
        result.recovery_result.hybrid_scene if result.recovery_result else None
    )
    if hybrid is None:
        return

    with get_session() as session:
        delivery = SlideRecoveryDeliveryService(session, settings=settings)
        source_path = delivery.resolve_source_preview_path(result)
        try:
            scene_preview = delivery.render_hybrid_preview(project_id, hybrid)
        except Exception:
            scene_preview = None

    if source_path is None and scene_preview is None:
        return

    st.markdown("#### 视觉预览")
    col_source, col_scene = st.columns(2)
    with col_source:
        st.caption("源页面")
        if source_path is not None and source_path.is_file():
            st.image(str(source_path), use_container_width=True)
        else:
            st.info("暂无源页面栅格预览。")
    with col_scene:
        st.caption("恢复 Hybrid Scene")
        if scene_preview is not None and scene_preview.is_file():
            st.image(str(scene_preview), use_container_width=True)
        else:
            st.info("场景预览暂不可用。")


def _render_delivery_actions(
    result: SlideRecoveryWorkflowResult,
    *,
    project_id: UUID,
    settings: Settings,
    key_prefix: str,
) -> None:
    hybrid = result.hybrid_scene or (
        result.recovery_result.hybrid_scene if result.recovery_result else None
    )
    if hybrid is None:
        return

    run = result.workflow_run
    can_export = run.status in {
        WorkflowStatus.COMPLETED,
        WorkflowStatus.AWAITING_REVIEW,
    }
    can_import = run.status == WorkflowStatus.COMPLETED

    st.markdown("#### 交付闭环")
    preset_options = list(EXPORT_POLICY_PRESETS.keys())
    default_index = preset_options.index("allow_hybrid")
    policy_preset = st.selectbox(
        "导出策略",
        options=preset_options,
        index=default_index,
        format_func=lambda key: EXPORT_POLICY_PRESETS[key],
        key=f"{key_prefix}_export_policy",
    )

    with get_session() as session:
        from archium.infrastructure.database.repositories import PresentationRepository

        deck_options = PresentationRepository(session).list_by_project(project_id)

    deck_labels = {str(item.id): item.title for item in deck_options}
    deck_ids = list(deck_labels.keys())
    selected_presentation: UUID | None = None
    if deck_ids:
        selected = st.selectbox(
            "导入目标汇报",
            options=deck_ids,
            format_func=lambda value: deck_labels[value],
            key=f"{key_prefix}_import_presentation",
        )
        selected_presentation = UUID(selected)
    else:
        st.caption("当前项目尚无汇报，导入时将自动创建「页面复活导入」。")

    col_export, col_import, col_template = st.columns(3)
    with col_export:
        if st.button(
            "导出混合 PPTX",
            key=f"{key_prefix}_export_pptx",
            disabled=not can_export,
        ):
            _run_export(
                project_id=project_id,
                result=result,
                hybrid=hybrid,
                policy_preset=policy_preset,
                settings=settings,
            )
    with col_import:
        if st.button(
            "导入到汇报",
            key=f"{key_prefix}_import_slide",
            type="primary",
            disabled=not can_import,
        ):
            _run_import(
                project_id=project_id,
                result=result,
                hybrid=hybrid,
                presentation_id=selected_presentation,
                settings=settings,
            )
    with col_template:
        if st.button(
            "保存为 Template Reference",
            key=f"{key_prefix}_save_template",
            disabled=not can_import,
        ):
            _run_save_template(
                project_id=project_id,
                result=result,
                hybrid=hybrid,
                settings=settings,
            )

    if run.status == WorkflowStatus.AWAITING_REVIEW:
        st.caption("复核通过后可导入到汇报；导出预览可在接受前进行。")

    return None


def _run_export(
    *,
    project_id: UUID,
    result: SlideRecoveryWorkflowResult,
    hybrid: HybridRenderScene,
    policy_preset: str,
    settings: Settings,
) -> None:
    try:
        with get_session() as session:
            delivery = SlideRecoveryDeliveryService(session, settings=settings)
            export_result = delivery.export_pptx(
                project_id,
                hybrid,
                source_page_id=result.source_page_id,
                policy_preset=policy_preset,
            )
            session.commit()
    except WorkflowError as exc:
        st.error(format_user_error(exc))
        return
    except Exception as exc:
        st.error(format_user_error(exc))
        return

    if export_result.pptx_export_skipped:
        st.warning("Node/PptxGenJS 不可用，已生成保真度清单但未写出 PPTX 文件。")
    elif export_result.pptx_path is not None:
        st.success(f"已导出：{export_result.pptx_path}")
        with contextlib.suppress(OSError):
            st.download_button(
                "下载 PPTX",
                data=export_result.pptx_path.read_bytes(),
                file_name=export_result.pptx_path.name,
                mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                key="slide_recovery_download_pptx",
            )

    manifest = export_result.manifest
    st.caption(
        f"导出保真度：{manifest.final_fidelity.value}"
        + (f" · 降级：{manifest.fallback_reason}" if manifest.fallback_used else "")
    )


def _run_import(
    *,
    project_id: UUID,
    result: SlideRecoveryWorkflowResult,
    hybrid: HybridRenderScene,
    presentation_id: UUID | None,
    settings: Settings,
) -> None:
    try:
        with get_session() as session:
            delivery = SlideRecoveryDeliveryService(session, settings=settings)
            import_result = delivery.import_to_presentation(
                project_id,
                hybrid,
                result.recovery_result,
                presentation_id=presentation_id,
            )
            session.commit()
    except WorkflowError as exc:
        st.error(format_user_error(exc))
        return
    except Exception as exc:
        st.error(format_user_error(exc))
        return

    st.success(
        f"已导入到汇报（第 {import_result.slide_order + 1} 页）。"
        f" Slide ID: {import_result.slide_id}"
    )
    if import_result.scene_preview_path and import_result.scene_preview_path.is_file():
        st.image(str(import_result.scene_preview_path), caption="导入后场景预览", width=480)


def _run_save_template(
    *,
    project_id: UUID,
    result: SlideRecoveryWorkflowResult,
    hybrid: HybridRenderScene,
    settings: Settings,
) -> None:
    try:
        with get_session() as session:
            delivery = SlideRecoveryDeliveryService(session, settings=settings)
            template_result = delivery.save_as_template_reference(
                project_id,
                hybrid,
                source_page_id=result.source_page_id,
                source_preview_path=delivery.resolve_source_preview_path(result),
            )
            session.commit()
    except WorkflowError as exc:
        st.error(format_user_error(exc))
        return
    except Exception as exc:
        st.error(format_user_error(exc))
        return

    st.success(
        f"已保存 Template Reference：{template_result.template.name}"
        f"（layout `{template_result.layout_id}`）"
    )
    if template_result.preview_path.is_file():
        st.image(
            str(template_result.preview_path),
            caption="Template Reference 预览",
            width=480,
        )
