"""Template Induction Review — classify / cluster / representative correction UI."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from archium.application.visual.template_induction_service import TemplateInductionService
from archium.domain.visual.template_induction import (
    ArchitecturalContentType,
    FunctionalSlideType,
    InductionReviewOverride,
    OutlineTemplateCoPlan,
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
    st.markdown("#### 1. 上传或打开参考 PPTX")
    open_path = st.text_input(
        "打开已有归纳工作区（induction_result.json 所在目录）",
        value=st.session_state.get("template_induction_workspace", ""),
        key="induction_workspace_path",
        placeholder="例如：output/phase35-validation/.../induction/<uuid>",
    )
    if st.button("打开工作区", use_container_width=True, key="induction_open_workspace"):
        path = Path(open_path.strip())
        if path.is_dir() and (path / "induction_result.json").is_file():
            st.session_state.template_induction_workspace = str(path)
            st.rerun()
        else:
            st.error("路径无效或缺少 induction_result.json")

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


def _render_phase35_signoff(service, workspace, presentation, induction) -> None:  # type: ignore[no-untyped-def]
    st.markdown("##### Phase 3.5 真人结构复核签署")
    signoff = induction.phase35_signoff
    if signoff:
        st.info(
            f"已签署：`{signoff.status}` · {signoff.reviewer or '（未署名）'}"
            + (f" · {signoff.run_reference}" if signoff.run_reference else "")
        )
        if signoff.notes:
            st.caption(signoff.notes)
    else:
        st.warning("尚未完成 Phase 3.5 真人签署 — 正式发布模板将被阻断。")

    with st.expander("记录 / 更新签署", expanded=signoff is None):
        status = st.selectbox(
            "签署结论",
            options=["PASS", "PASS_WITH_WARNINGS", "NEEDS_REVIEW", "BLOCKED"],
            index=1 if signoff is None else ["PASS", "PASS_WITH_WARNINGS", "NEEDS_REVIEW", "BLOCKED"].index(signoff.status),
            key="phase35_signoff_status",
        )
        reviewer = st.text_input("复核人", value=signoff.reviewer if signoff else "", key="phase35_reviewer")
        run_ref = st.text_input(
            "Run 引用",
            value=signoff.run_reference if signoff else "",
            placeholder="phase35_20260721_074113",
            key="phase35_run_ref",
        )
        notes = st.text_area("备注", value=signoff.notes if signoff else "", key="phase35_notes")
        if st.button("保存签署", key="phase35_save_signoff"):
            if not reviewer.strip():
                st.error("请填写复核人")
            else:
                service.record_phase35_signoff(
                    induction,
                    status=status,
                    reviewer=reviewer,
                    notes=notes,
                    run_reference=run_ref,
                    workspace=workspace,
                    presentation=presentation,
                )
                st.success("已保存 Phase 3.5 签署")
                st.rerun()


def _render_publication_readiness(presentation, induction) -> None:  # type: ignore[no-untyped-def]
    from archium.application.visual.architectural_content_schema_publish_gate import (
        ArchitecturalContentSchemaPublishGate,
    )
    from archium.application.visual.template_publication_readiness import (
        TemplatePublicationReadinessService,
    )
    from archium.domain.visual.architectural_content_schema import (
        ArchitecturalContentSchema,
        SchemaPublishReport,
    )

    schemas = [
        ArchitecturalContentSchema.model_validate(item) for item in induction.content_schemas
    ]
    if not schemas:
        return

    report_raw = induction.publish_report or {}
    publish_report = (
        SchemaPublishReport.model_validate(report_raw) if report_raw else None
    )
    if publish_report is None:
        publish_report = ArchitecturalContentSchemaPublishGate().evaluate(
            induction=induction,
            presentation=presentation,
            schemas=schemas,
            formal_publish=True,
        )

    readiness = TemplatePublicationReadinessService().evaluate(
        induction=induction,
        presentation=presentation,
        schemas=schemas,
        publish_report=publish_report,
    )

    st.markdown("##### 正式发布门槛（Phase 4）")
    st.caption(f"综合：`{readiness.overall}` · 可正式发布：{'是' if readiness.can_formally_publish else '否'}")
    for gate in readiness.gates:
        if gate.status == "PASS":
            st.success(f"{gate.label} — {gate.detail}")
        elif gate.status == "PASS_WITH_WARNINGS":
            st.warning(f"{gate.label} — {gate.detail}")
        elif gate.status in {"BLOCKED", "NEEDS_REVIEW"}:
            st.error(f"{gate.label} — {gate.detail}")
        else:
            st.info(f"{gate.label} — {gate.detail}")


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

    _render_phase35_signoff(service, workspace, presentation, induction)
    manifest = workspace / "phase4_review_manifest.md"
    if manifest.is_file():
        st.caption(f"复核清单：`{manifest.name}`（可用 `run_phase4_review_manifest.py` 重新生成）")
    _render_publication_readiness(presentation, induction)

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
    st.caption("可移动页面、合并聚类、拆分为新聚类。保存后写入 content_clusters.json。")

    from archium.application.visual.induction_cluster_editor import (
        layout_from_clusters,
        merge_clusters,
        move_slide,
        split_slide,
    )

    workspace_key = str(workspace)
    if st.session_state.get("induction_cluster_workspace") != workspace_key:
        st.session_state.induction_cluster_workspace = workspace_key
        st.session_state.induction_cluster_layout = layout_from_clusters(induction.clusters)

    cluster_layout: dict[str, list[str]] = dict(
        st.session_state.get("induction_cluster_layout", layout_from_clusters(induction.clusters))
    )
    cluster_by_id = {c.id: c for c in induction.clusters}

    for cluster_id, member_ids in sorted(
        cluster_layout.items(),
        key=lambda item: (
            min(
                next(
                    (s.slide_index for s in presentation.slides if s.slide_id == sid),
                    10_000,
                )
                for sid in item[1]
            )
            if item[1]
            else 10_000,
            item[0],
        ),
    ):
        meta = cluster_by_id.get(cluster_id)
        label_type = (
            f"{meta.functional_type.value}/{meta.content_type.value}"
            if meta
            else "edited"
        )
        with st.expander(
            f"聚类 {cluster_id[:8]} · {label_type} · {len(member_ids)} 页",
            expanded=meta is not None
            and meta.functional_type == FunctionalSlideType.CONTENT,
        ):
            if len(member_ids) <= 1:
                st.caption("单页聚类 — 可使用下方「拆分为新聚类」调整其他页。")
            merge_targets = [
                cid for cid in cluster_layout if cid != cluster_id and cluster_layout[cid]
            ]
            if merge_targets and len(member_ids) > 0:

                def _cluster_label(cid: str, layout: dict[str, list[str]] = cluster_layout) -> str:
                    return f"{cid[:8]} ({len(layout[cid])} 页)"

                mcol1, mcol2 = st.columns([3, 1])
                with mcol1:
                    merge_into = st.selectbox(
                        "合并此聚类到",
                        options=merge_targets,
                        format_func=_cluster_label,
                        key=f"merge_target_{cluster_id}",
                    )
                with mcol2:
                    if st.button("合并", key=f"merge_btn_{cluster_id}", use_container_width=True):
                        cluster_layout = merge_clusters(cluster_layout, cluster_id, merge_into)
                        st.session_state.induction_cluster_layout = cluster_layout
                        st.rerun()

            for slide_id in member_ids:
                slide = next((s for s in presentation.slides if s.slide_id == slide_id), None)
                row1, row2, row3 = st.columns([2, 2, 1])
                with row1:
                    st.write(slide_id)
                    if slide and slide.text_content:
                        st.caption(slide.text_content[0][:80])
                move_targets = [
                    cid
                    for cid in cluster_layout
                    if cid != cluster_id and cluster_layout.get(cid) is not None
                ]
                with row2:
                    if move_targets:
                        dest = st.selectbox(
                            "移动到",
                            options=move_targets,
                            format_func=lambda cid: cid[:8],
                            key=f"move_dest_{cluster_id}_{slide_id}",
                        )
                        if st.button(
                            "移动",
                            key=f"move_btn_{cluster_id}_{slide_id}",
                            use_container_width=True,
                        ):
                            cluster_layout = move_slide(cluster_layout, slide_id, dest)
                            st.session_state.induction_cluster_layout = cluster_layout
                            st.rerun()
                with row3:
                    if st.button(
                        "拆分",
                        key=f"split_btn_{cluster_id}_{slide_id}",
                        use_container_width=True,
                    ):
                        cluster_layout, _new_id = split_slide(cluster_layout, slide_id)
                        st.session_state.induction_cluster_layout = cluster_layout
                        st.rerun()

            rep_options = member_ids or [""]
            current_rep = (
                meta.representative_slide_id
                if meta and meta.representative_slide_id in member_ids
                else rep_options[0]
            )
            choice = st.selectbox(
                "代表页面",
                options=rep_options,
                index=rep_options.index(current_rep) if current_rep in rep_options else 0,
                key=f"rep_{cluster_id}",
            )
            st.session_state.setdefault("induction_rep_overrides", {})
            st.session_state["induction_rep_overrides"][cluster_id] = choice

    st.session_state.induction_cluster_layout = cluster_layout

    st.markdown("##### 内容 Schema（Phase 4 · 开发放行 / 正式发布有条件）")
    st.caption(
        "自动归纳的 Schema 可用于开发与测试；仅当发布门为 `PASS` 且无阻断项时，"
        "「正式发布模板」才会写入 `published` 状态。`PASS_WITH_WARNINGS` 仅表示可继续复核。"
    )
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
        blockers_raw = report_raw.get("blockers")
        if isinstance(blockers_raw, list):
            for blocker in blockers_raw:
                if isinstance(blocker, dict):
                    st.error(f"{blocker.get('code')}: {blocker.get('message')}")
        warnings_raw = report_raw.get("warnings")
        if isinstance(warnings_raw, list):
            for warning in warnings_raw:
                st.warning(str(warning))
        fills_raw = report_raw.get("test_fill_results")
        if isinstance(fills_raw, list) and fills_raw:
            st.markdown("**测试内容填充**")
            for fill in fills_raw:
                if not isinstance(fill, dict):
                    continue
                ok = fill.get("render_valid")
                sid = fill.get("representative_slide_id", "")
                label = "通过" if ok else "未通过"
                st.write(f"- `{sid}` · {label}")

    col_a, col_b = st.columns(2)
    save_clicked = col_a.button("保存修正", type="primary", use_container_width=True)
    publish_clicked = col_b.button("正式发布模板（需 PASS）", use_container_width=True)

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
        updated = service.apply_overrides(
            induction,
            presentation,
            overrides,
            cluster_layout=st.session_state.get("induction_cluster_layout"),
        )
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
        if report.can_formally_publish:
            try:
                mat = service.materialize_architectural_template(
                    induction, presentation, workspace, schemas=schemas
                )
                st.success(
                    f"模板已正式发布 · ArchitecturalTemplate `{mat.template.id}` "
                    f"（{len(mat.template.layouts)} layouts）"
                )
            except Exception as exc:  # noqa: BLE001
                st.warning(f"Schema 已 published，但 ArchitecturalTemplate 物化失败：{exc}")
        elif report.can_publish:
            st.warning(
                f"发布门为 `{report.status}`，尚有警告未清除，未写入 published 状态。"
            )
        else:
            st.error(f"发布被阻断：{report.status}")
        st.rerun()

    st.markdown("##### 产物路径")
    st.code(str(workspace), language="text")
    st.caption(
        "输出：reference_presentation.json · slides/ · "
        "functional_classification.json · content_clusters.json · "
        "representative_slides.json · content_schemas.json · "
        "schema_publish_report.json · architectural_template.json · "
        "outline_template_co_plan.json（协同规划后）"
    )


def _render_co_plan() -> None:
    workspace = _selected_workspace()
    if workspace is None:
        return

    st.divider()
    st.markdown("#### Outline–Template 协同规划（Phase 5 · 实验性）")
    st.caption(
        "将大纲章节映射到已归纳 Schema：模板亲和 / 兼容检查 / "
        "未匹配模板页暴露 / Free Composition fallback。"
        "可对 ``template_editing`` 路由执行参考页编辑式 Scene 生成（Phase 6 骨架）。"
        "实验性功能；在至少一套真实模板正式发布前，不得用于真实交付物生成。"
    )
    scenario = st.radio(
        "示例大纲",
        options=["老旧建筑改造", "文化名村"],
        horizontal=True,
        key="induction_co_plan_scenario",
    )
    if not st.button("生成协同规划", key="induction_run_co_plan", use_container_width=True):
        service = TemplateInductionService()
        co_plan = service.load_co_plan(workspace)
        if co_plan is not None:
            _show_co_plan(co_plan, workspace=workspace)
            _render_template_editing_panel(workspace, co_plan)
        return

    from uuid import uuid4

    from archium.application.outline_templates import (
        cultural_village_outline_sections,
        renovation_outline_sections,
    )
    from archium.domain.outline import OutlinePlan

    service = TemplateInductionService()
    try:
        _presentation, induction = service.load_workspace(workspace)
    except Exception as exc:  # noqa: BLE001
        st.error(format_user_error(exc))
        return

    sections = (
        renovation_outline_sections()
        if scenario == "老旧建筑改造"
        else cultural_village_outline_sections()
    )
    outline = OutlinePlan(
        presentation_id=uuid4(),
        title=scenario,
        thesis="以证据支持汇报决策",
        audience="主管部门",
        purpose="协同规划演示",
        sections=sections,
        target_slide_count=max(1, sum(s.estimated_slide_count for s in sections)),
    )
    template = service.load_architectural_template(workspace)
    co_plan = service.co_plan_outline(
        induction, outline, workspace=workspace, template=template
    )
    st.success(
        f"已规划 {co_plan.planned_page_count} 页 · "
        f"模板编辑 {len(co_plan.template_editing_page_ids)} · "
        f"自由构图 {len(co_plan.free_composition_page_ids)} · "
        f"需人工 {len(co_plan.manual_required_page_ids)}"
    )
    _show_co_plan(co_plan, workspace=workspace)
    _render_template_editing_panel(workspace, co_plan)


def _render_template_editing_panel(workspace: Path, co_plan: OutlineTemplateCoPlan) -> None:
    from archium.application.visual.template_induction_service import TemplateInductionService
    from archium.domain.visual.template_induction import OutlineTemplateEditingBatch

    if not co_plan.template_editing_page_ids:
        return

    st.markdown("##### 模板编辑路由（Phase 6 · 骨架）")
    st.caption(
        f"{len(co_plan.template_editing_page_ids)} 页路由为 template_editing，"
        "将参考页结构复制为 RenderScene 并剥离 reference 内容。"
    )
    service = TemplateInductionService()
    existing_batch = service.load_template_editing_batch(workspace)
    if existing_batch is not None:
        st.info(
            f"已有编辑批次：生成 {existing_batch.generated_count} · "
            f"跳过 {existing_batch.skipped_count} · "
            f"失败 {existing_batch.failed_count}"
        )

    if st.button("执行 template_editing 路由", key="induction_run_template_editing"):
        outline = service.load_outline_plan(workspace)
        if outline is None:
            st.error("缺少 outline_plan.json，请重新生成协同规划。")
            return
        try:
            presentation, induction = service.load_workspace(workspace)
            template = service.load_architectural_template(workspace)
            if template is None:
                st.error("缺少 architectural_template.json，请先 materialize 归纳模板。")
                return
            batch, updated = service.execute_co_plan_template_editing(
                induction,
                outline,
                co_plan,
                presentation,
                template=template,
                workspace=workspace,
            )
        except Exception as exc:  # noqa: BLE001
            st.error(format_user_error(exc))
            return
        st.success(
            f"模板编辑完成：生成 {batch.generated_count} · "
            f"跳过 {batch.skipped_count} · 失败 {batch.failed_count}"
        )
        _show_co_plan(updated, workspace=workspace)
        _show_template_editing_batch(batch)


def _show_template_editing_batch(batch: OutlineTemplateEditingBatch) -> None:
    rows = []
    for page in batch.page_results[:40]:
        rows.append(
            {
                "page": page.slide_id,
                "status": page.status,
                "nodes": page.node_count,
                "stripped_text": page.stripped_text_count,
                "stripped_asset": page.stripped_asset_count,
                "scene": page.edit_scene_relative_path or "",
                "error": page.error[:80] if page.error else "",
            }
        )
    if rows:
        st.dataframe(rows, use_container_width=True, hide_index=True)
    for warning in batch.warnings:
        st.warning(warning)


def _show_co_plan(co_plan: OutlineTemplateCoPlan, *, workspace: Path | None = None) -> None:
    for warning in co_plan.warnings:
        st.warning(warning)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("规划页", co_plan.planned_page_count)
    c2.metric("模板编辑", len(co_plan.template_editing_page_ids))
    c3.metric("自由构图", len(co_plan.free_composition_page_ids))
    c4.metric("需人工", len(co_plan.manual_required_page_ids))
    if co_plan.unmatched_schema_ids:
        st.caption(
            f"未匹配 Schema（暴露）：{len(co_plan.unmatched_schema_ids)} 个 — "
            + ", ".join(co_plan.unmatched_schema_ids[:6])
        )
    rows = []
    for page in co_plan.page_plans[:40]:
        rows.append(
            {
                "section": page.section_title or page.section_id,
                "page": page.slide_id,
                "content": page.inferred_content_type.value,
                "affinity": page.template_affinity,
                "mode": page.fallback_mode,
                "edit": page.edit_scene_status,
                "schema": (page.schema_id or "")[:8],
            }
        )
    if rows:
        st.dataframe(rows, use_container_width=True, hide_index=True)
    if workspace is not None:
        scenes_dir = workspace / "co_plan_scenes"
        if scenes_dir.is_dir():
            scene_count = sum(1 for _ in scenes_dir.rglob("render_scene.json"))
            if scene_count:
                st.caption(f"已写入 {scene_count} 个 RenderScene 至 co_plan_scenes/")


def render() -> None:
    st.title("模板归纳复核")
    st.caption(
        "从参考 PPTX 归纳功能页、内容聚类与建筑内容 Schema，"
        "并支持 Outline–Template 协同规划（实验性）。"
        "Phase 4 可开发测试；正式发布需通过发布门且完成 Phase 3.5 人工复核。"
        "Phase 6 参考页编辑式生成已接 Co-plan template_editing 路由（骨架）。"
    )
    _render_upload()
    st.divider()
    _render_review()
    _render_co_plan()


def render_page() -> None:
    render()
