"""Template Induction Review — classify / cluster / representative correction UI."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

import streamlit as st

from archium.application.visual.template_induction_service import TemplateInductionService
from archium.domain.visual.template_induction import (
    ArchitecturalContentType,
    FunctionalSlideType,
    InductionReviewOverride,
)
from archium.exceptions import WorkflowError
from archium.ui.error_handlers import format_user_error


def _selected_workspace() -> Path | None:
    raw = st.session_state.get("template_induction_workspace")
    if not raw:
        return None
    path = Path(str(raw))
    return path if path.is_dir() else None


def _render_upload() -> None:
    st.markdown("#### 1. 上传参考 PPTX")
    uploaded = st.file_uploader(
        "选择建筑参考汇报（建议 ≥15 页）",
        type=["pptx", "pptm"],
        key="induction_pptx",
    )
    name = st.text_input("归纳名称", value="", placeholder="例如：院区改造参考模板")
    if st.button("开始归纳", type="primary", disabled=uploaded is None, use_container_width=True):
        if uploaded is None:
            return
        from archium.config.settings import get_settings

        staging = get_settings().output_path / "template-induction" / "_upload_staging"
        staging.mkdir(parents=True, exist_ok=True)
        staged = staging / uploaded.name
        staged.write_bytes(uploaded.getvalue())
        with st.spinner("解析页面 · 功能分类 · 内容聚类 · 代表页选择…"):
            try:
                result = TemplateInductionService().induce(
                    staged,
                    name=name.strip() or Path(uploaded.name).stem,
                )
            except WorkflowError as exc:
                st.error(format_user_error(exc))
                return
            except Exception as exc:  # noqa: BLE001
                st.error(format_user_error(exc))
                return
        st.session_state.template_induction_workspace = str(result.workspace)
        st.success(
            f"已归纳「{result.induction.name}」：{result.induction.slide_count} 页 · "
            f"{len(result.induction.clusters)} 个聚类 · "
            f"待复核 {len(result.induction.low_confidence_slide_ids)} 页"
        )
        for warning in result.induction.warnings:
            st.warning(warning)
        st.rerun()


def _render_review() -> None:
    workspace = _selected_workspace()
    if workspace is None:
        st.info("请先上传参考 PPTX 完成自动归纳。")
        return

    service = TemplateInductionService()
    try:
        presentation, induction = service.load_workspace(workspace)
    except Exception as exc:  # noqa: BLE001
        st.error(format_user_error(exc))
        return

    st.markdown("#### 2. 人工快速修正（非评分）")
    st.caption(
        "只需修正：页面类型 · 聚类归属 · 代表页 · 内容类型。不要打 1–5 分。"
    )
    cols = st.columns(4)
    cols[0].metric("页数", induction.slide_count)
    cols[1].metric("聚类", len(induction.clusters))
    content_clusters = sum(
        1 for c in induction.clusters if c.functional_type == FunctionalSlideType.CONTENT
    )
    cols[2].metric("内容聚类", content_clusters)
    cols[3].metric("待复核", len(induction.low_confidence_slide_ids))

    st.markdown("##### 功能分类")
    for clf in induction.classifications:
        slide = next((s for s in presentation.slides if s.slide_id == clf.slide_id), None)
        with st.expander(
            f"{clf.slide_id} · {clf.functional_type.value} / {clf.content_type.value} · "
            f"置信度 {clf.confidence:.2f}"
            + (" · 需复核" if clf.needs_review else ""),
            expanded=clf.needs_review,
        ):
            left, right = st.columns([1, 1])
            with left:
                if slide and slide.image_path:
                    img = workspace / slide.image_path
                    if img.is_file():
                        st.image(str(img), use_container_width=True)
                    else:
                        st.caption("暂无截图")
                else:
                    st.caption("暂无截图")
                if slide:
                    st.write("文本摘录：")
                    for chunk in slide.text_content[:4]:
                        st.caption(chunk[:120])
            with right:
                ft = st.selectbox(
                    "功能类型",
                    options=[t.value for t in FunctionalSlideType],
                    index=[t.value for t in FunctionalSlideType].index(clf.functional_type.value),
                    key=f"ft_{clf.slide_id}",
                )
                ct = st.selectbox(
                    "内容类型",
                    options=[t.value for t in ArchitecturalContentType],
                    index=[t.value for t in ArchitecturalContentType].index(
                        clf.content_type.value
                    ),
                    key=f"ct_{clf.slide_id}",
                )
                st.caption("依据：" + "；".join(clf.evidence[:4]))
                st.session_state.setdefault("induction_overrides", {})
                st.session_state["induction_overrides"][clf.slide_id] = {
                    "functional_type": ft,
                    "content_type": ct,
                }

    st.markdown("##### 聚类与代表页")
    for cluster in induction.clusters:
        with st.expander(
            f"聚类 {cluster.id[:8]} · {cluster.functional_type.value}/"
            f"{cluster.content_type.value} · {len(cluster.slide_ids)} 页 · "
            f"代表 {cluster.representative_slide_id}",
            expanded=cluster.functional_type == FunctionalSlideType.CONTENT,
        ):
            st.write("成员：", ", ".join(cluster.slide_ids))
            st.caption("；".join(cluster.selection_rationale[:5]))
            choice = st.selectbox(
                "代表页面",
                options=cluster.slide_ids,
                index=cluster.slide_ids.index(cluster.representative_slide_id)
                if cluster.representative_slide_id in cluster.slide_ids
                else 0,
                key=f"rep_{cluster.id}",
            )
            st.session_state.setdefault("induction_rep_overrides", {})
            st.session_state["induction_rep_overrides"][cluster.id] = choice

    st.markdown("##### 内容 Schema（Phase 4）")
    from archium.domain.visual.architectural_content_schema import (
        ArchitecturalContentSchema,
        SchemaReviewOverride,
    )

    schemas = [
        ArchitecturalContentSchema.model_validate(item)
        for item in induction.content_schemas
    ]
    if not schemas:
        st.info("尚无 Schema，请先保存分类/代表页修正以重新提取。")
    for schema in schemas:
        with st.expander(
            f"{schema.name} · 代表 {schema.representative_slide_id} · "
            f"置信度 {schema.confidence:.2f}"
            + (" · 需确认" if schema.needs_review and not schema.human_corrected else ""),
            expanded=schema.needs_review and not schema.human_corrected,
        ):
            st.write(schema.page_purpose)
            st.caption(
                "必填角色："
                + ", ".join(sorted(schema.required_roles()) or ["（无）"])
            )
            slots = ", ".join(v.role for v in schema.visual_requirements) or "（无）"
            st.caption("视觉槽位：" + slots)
            purpose = st.text_area(
                "页面用途",
                value=schema.page_purpose,
                key=f"schema_purpose_{schema.id}",
            )
            c1, c2, c3 = st.columns(3)
            supports_drawing = c1.checkbox(
                "允许图纸",
                value=schema.supports_drawing,
                key=f"schema_drawing_{schema.id}",
            )
            citation_required = c2.checkbox(
                "需要引用",
                value=schema.citation_required,
                key=f"schema_cite_{schema.id}",
            )
            caption_required = c3.checkbox(
                "需要图注",
                value=schema.caption_required,
                key=f"schema_cap_{schema.id}",
            )
            allowed = st.multiselect(
                "允许素材来源",
                options=[
                    "project_upload",
                    "public_research",
                    "reference_case",
                    "stock_image",
                ],
                default=[o for o in schema.allowed_asset_origins if o != "reference_template"],
                key=f"schema_allowed_{schema.id}",
            )
            st.session_state.setdefault("induction_schema_overrides", {})
            st.session_state["induction_schema_overrides"][schema.id] = {
                "page_purpose": purpose,
                "supports_drawing": supports_drawing,
                "citation_required": citation_required,
                "caption_required": caption_required,
                "allowed_asset_origins": allowed,
            }

    report_raw = induction.publish_report or {}
    if report_raw:
        st.markdown("##### 发布门禁")
        st.write(f"状态：`{report_raw.get('status', 'UNKNOWN')}`")
        for blocker in report_raw.get("blockers") or []:
            if isinstance(blocker, dict):
                st.error(f"{blocker.get('code')}: {blocker.get('message')}")
        for warning in report_raw.get("warnings") or []:
            st.warning(str(warning))

    col_a, col_b = st.columns(2)
    save_clicked = col_a.button("保存修正", type="primary", use_container_width=True)
    publish_clicked = col_b.button("尝试发布 Schema", use_container_width=True)

    if save_clicked:
        overrides: list[InductionReviewOverride] = []
        type_map = st.session_state.get("induction_overrides", {})
        for slide_id, payload in type_map.items():
            overrides.append(
                InductionReviewOverride(
                    slide_id=slide_id,
                    functional_type=FunctionalSlideType(payload["functional_type"]),
                    content_type=ArchitecturalContentType(payload["content_type"]),
                )
            )
        for cluster_id, slide_id in st.session_state.get("induction_rep_overrides", {}).items():
            overrides.append(
                InductionReviewOverride(
                    slide_id=slide_id,
                    cluster_id=cluster_id,
                    is_representative=True,
                )
            )
        updated = service.apply_overrides(induction, presentation, overrides)
        schema_overrides = [
            SchemaReviewOverride(
                schema_id=schema_id,
                page_purpose=payload.get("page_purpose"),
                supports_drawing=payload.get("supports_drawing"),
                citation_required=payload.get("citation_required"),
                caption_required=payload.get("caption_required"),
                allowed_asset_origins=payload.get("allowed_asset_origins"),
                forbidden_asset_origins=["reference_template", "ai_generated"],
            )
            for schema_id, payload in st.session_state.get(
                "induction_schema_overrides", {}
            ).items()
        ]
        updated, schemas, report = service.apply_schema_overrides(
            updated, presentation, schema_overrides
        )
        service.export_artifacts(
            workspace, presentation, updated, schemas=schemas, publish_report=report
        )
        st.success("已保存人工修正，并更新 Schema / 聚类产物。")
        st.rerun()

    if publish_clicked:
        schemas = [
            ArchitecturalContentSchema.model_validate(item)
            for item in induction.content_schemas
        ]
        report = service.publish(induction, presentation, schemas=schemas)
        service.export_artifacts(
            workspace, presentation, induction, schemas=schemas, publish_report=report
        )
        if report.can_publish:
            st.success(f"Schema 可发布：{report.status}")
        else:
            st.error(f"发布被阻断：{report.status}")
        st.rerun()

    st.markdown("##### 产物路径")
    st.code(str(workspace), language="text")
    st.caption(
        "输出：reference_presentation.json · slides/ · "
        "functional_classification.json · content_clusters.json · "
        "representative_slides.json · content_schemas.json · schema_publish_report.json"
    )


def render() -> None:
    st.title("模板归纳复核")
    st.caption(
        "从参考 PPTX 归纳功能页、内容聚类与建筑内容 Schema。"
        "人工只做修正，不打分。本阶段不做编辑式生成。"
    )
    _render_upload()
    st.divider()
    _render_review()


def render_page() -> None:
    render()
