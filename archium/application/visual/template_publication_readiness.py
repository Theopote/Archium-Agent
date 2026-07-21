"""Five-gate readiness report for Phase 4 formal template publication."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from archium.domain._base import DomainModel
from archium.domain.visual.architectural_content_schema import (
    ArchitecturalContentSchema,
    SchemaPublishReport,
)
from archium.domain.visual.reference_slide import ReferencePresentation
from archium.domain.visual.template_induction import (
    FunctionalSlideType,
    TemplateInductionResult,
)


class PublicationGateItem(DomainModel):
    gate_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    status: Literal["PASS", "PASS_WITH_WARNINGS", "NEEDS_REVIEW", "BLOCKED", "PENDING"]
    detail: str = ""


class TemplatePublicationReadiness(DomainModel):
    gates: list[PublicationGateItem] = Field(default_factory=list)
    overall: Literal["PASS", "PASS_WITH_WARNINGS", "NEEDS_REVIEW", "BLOCKED", "PENDING"] = (
        "PENDING"
    )
    can_formally_publish: bool = False

    @property
    def pending_gate_ids(self) -> list[str]:
        return [g.gate_id for g in self.gates if g.status in {"PENDING", "BLOCKED", "NEEDS_REVIEW"}]


class TemplatePublicationReadinessService:
    """Evaluate the five Phase 4 formal publication gates."""

    def evaluate(
        self,
        *,
        induction: TemplateInductionResult,
        presentation: ReferencePresentation,
        schemas: list[ArchitecturalContentSchema],
        publish_report: SchemaPublishReport | None = None,
    ) -> TemplatePublicationReadiness:
        gates: list[PublicationGateItem] = []

        signoff = induction.phase35_signoff
        if signoff is None:
            gates.append(
                PublicationGateItem(
                    gate_id="phase35_human_signoff",
                    label="Phase 3.5 真人结构复核签署",
                    status="PENDING",
                    detail="尚未记录 phase35_human_signoff",
                )
            )
        elif signoff.allows_formal_publish:
            gates.append(
                PublicationGateItem(
                    gate_id="phase35_human_signoff",
                    label="Phase 3.5 真人结构复核签署",
                    status="PASS_WITH_WARNINGS"
                    if signoff.status == "PASS_WITH_WARNINGS"
                    else "PASS",
                    detail=f"{signoff.reviewer or 'reviewer'} · {signoff.status}"
                    + (f" · {signoff.run_reference}" if signoff.run_reference else ""),
                )
            )
        else:
            gates.append(
                PublicationGateItem(
                    gate_id="phase35_human_signoff",
                    label="Phase 3.5 真人结构复核签署",
                    status="BLOCKED",
                    detail=f"签署状态为 {signoff.status}，不可正式发布",
                )
            )

        rep_unconfirmed = [
            c.id
            for c in induction.clusters
            if c.representative_slide_id
            and (clf := induction.classification_for(c.representative_slide_id)) is not None
            and clf.needs_review
        ]
        if rep_unconfirmed:
            gates.append(
                PublicationGateItem(
                    gate_id="representative_classification",
                    label="代表页低置信分类",
                    status="BLOCKED",
                    detail=f"{len(rep_unconfirmed)} 个聚类代表页待复核",
                )
            )
        else:
            gates.append(
                PublicationGateItem(
                    gate_id="representative_classification",
                    label="代表页低置信分类",
                    status="PASS",
                    detail="全部代表页分类已确认",
                )
            )

        content_schemas = [
            s
            for s in schemas
            if s.functional_type == FunctionalSlideType.CONTENT
            or any(
                c.id == s.cluster_id and c.functional_type == FunctionalSlideType.CONTENT
                for c in induction.clusters
            )
        ]
        missing_stats = [
            s.id
            for s in content_schemas
            if s.cluster_member_count > 1 and not s.cluster_stats
        ]
        if missing_stats:
            gates.append(
                PublicationGateItem(
                    gate_id="cluster_level_schema",
                    label="Cluster-level Schema 统计",
                    status="NEEDS_REVIEW",
                    detail=f"{len(missing_stats)} 个 Schema 缺少 cluster_stats",
                )
            )
        elif content_schemas:
            gates.append(
                PublicationGateItem(
                    gate_id="cluster_level_schema",
                    label="Cluster-level Schema 统计",
                    status="PASS",
                    detail=f"{len(content_schemas)} 个内容 Schema 含聚类统计",
                )
            )
        else:
            gates.append(
                PublicationGateItem(
                    gate_id="cluster_level_schema",
                    label="Cluster-level Schema 统计",
                    status="BLOCKED",
                    detail="无内容 Schema",
                )
            )

        if publish_report is None or not publish_report.test_fill_results:
            gates.append(
                PublicationGateItem(
                    gate_id="schema_test_fill",
                    label="Schema 测试内容填充",
                    status="PENDING",
                    detail="尚无 test_fill_results（请运行发布门评估）",
                )
            )
        else:
            failed = [f for f in publish_report.test_fill_results if not f.render_valid]
            compiled = [f for f in publish_report.test_fill_results if f.scene_compiled]
            if failed:
                gates.append(
                    PublicationGateItem(
                        gate_id="schema_test_fill",
                        label="Schema 测试内容填充",
                        status="BLOCKED",
                        detail=(
                            f"{len(failed)}/{len(publish_report.test_fill_results)} "
                            f"未通过 RenderScene 测试填充"
                            f"（已编译 {len(compiled)}）"
                        ),
                    )
                )
            else:
                gates.append(
                    PublicationGateItem(
                        gate_id="schema_test_fill",
                        label="Schema 测试内容填充",
                        status="PASS",
                        detail=(
                            f"{len(publish_report.test_fill_results)} 个 Schema "
                            f"RenderScene 测试填充通过"
                        ),
                    )
                )

        if induction.status.value == "published" and publish_report and publish_report.can_formally_publish:
            if induction.architectural_template_id:
                gates.append(
                    PublicationGateItem(
                        gate_id="real_template_published",
                        label="真实模板正式发布",
                        status="PASS",
                        detail=(
                            f"induction.status=published · ArchitecturalTemplate "
                            f"{induction.architectural_template_id}"
                        ),
                    )
                )
            else:
                gates.append(
                    PublicationGateItem(
                        gate_id="real_template_published",
                        label="真实模板正式发布",
                        status="PENDING",
                        detail="Schema 已 published，待 materialize ArchitecturalTemplate",
                    )
                )
        elif publish_report and publish_report.can_formally_publish:
            gates.append(
                PublicationGateItem(
                    gate_id="real_template_published",
                    label="真实模板正式发布",
                    status="PENDING",
                    detail="发布门已达 PASS，待执行「正式发布模板」",
                )
            )
        else:
            blocker_codes = (
                [b.code for b in publish_report.blockers]
                if publish_report
                else []
            )
            gates.append(
                PublicationGateItem(
                    gate_id="real_template_published",
                    label="真实模板正式发布",
                    status="BLOCKED"
                    if publish_report and publish_report.status == "BLOCKED"
                    else "PENDING",
                    detail="发布门未达 PASS"
                    + (f" · {', '.join(blocker_codes[:3])}" if blocker_codes else ""),
                )
            )

        statuses = {g.status for g in gates}
        overall: Literal["PASS", "PASS_WITH_WARNINGS", "NEEDS_REVIEW", "BLOCKED", "PENDING"]
        if "BLOCKED" in statuses:
            overall = "BLOCKED"
        elif "PENDING" in statuses or "NEEDS_REVIEW" in statuses:
            overall = "NEEDS_REVIEW"
        elif "PASS_WITH_WARNINGS" in statuses:
            overall = "PASS_WITH_WARNINGS"
        else:
            overall = "PASS"

        can_formally_publish = (
            overall == "PASS"
            and publish_report is not None
            and publish_report.can_formally_publish
            and induction.phase35_signoff is not None
            and induction.phase35_signoff.allows_formal_publish
        )

        return TemplatePublicationReadiness(
            gates=gates,
            overall=overall,
            can_formally_publish=can_formally_publish,
        )
