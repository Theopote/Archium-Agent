"""Template induction pipeline: parse → classify → cluster → representatives → export."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

from archium.application.visual.asset_path_resolver import is_machine_absolute_path
from archium.application.visual.functional_slide_classifier import FunctionalSlideClassifier
from archium.application.visual.reference_slide_clusterer import ReferenceSlideClusterer
from archium.application.visual.representative_slide_selector import RepresentativeSlideSelector
from archium.config.settings import Settings, get_settings
from archium.domain.visual.reference_slide import ReferencePresentation, ReferenceSlideSnapshot
from archium.domain.visual.template_induction import (
    FunctionalSlideClassification,
    InductionReviewOverride,
    ReferenceSlideCluster,
    RepresentativeSlideScore,
    TemplateInductionResult,
    TemplateInductionStatus,
)
from archium.exceptions import WorkflowError
from archium.infrastructure.template.reference_pptx_parser import ReferencePptxParser


@dataclass(frozen=True)
class TemplateInductionRunResult:
    induction: TemplateInductionResult
    presentation: ReferencePresentation
    workspace: Path
    artifact_paths: dict[str, Path]
    screenshot_count: int = 0
    screenshot_tools_available: bool = False


class TemplateInductionService:
    """Phase 0–3 induction without edit-based generation or parallel PPT kernels."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        parser: ReferencePptxParser | None = None,
        classifier: FunctionalSlideClassifier | None = None,
        clusterer: ReferenceSlideClusterer | None = None,
        selector: RepresentativeSlideSelector | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._parser = parser or ReferencePptxParser()
        self._classifier = classifier or FunctionalSlideClassifier()
        self._clusterer = clusterer or ReferenceSlideClusterer()
        self._selector = selector or RepresentativeSlideSelector()

    def workspace_root(self, induction_id: UUID | str) -> Path:
        path = self._settings.output_path / "template-induction" / str(induction_id)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def induce(
        self,
        pptx_path: Path | str,
        *,
        name: str | None = None,
        induction_id: UUID | None = None,
        capture_screenshots: bool = True,
        require_screenshots: bool = False,
    ) -> TemplateInductionRunResult:
        from archium.infrastructure.renderers.pptx_screenshot import screenshot_tools_available

        source = Path(pptx_path)
        if not source.is_file():
            raise WorkflowError(f"参考 PPTX 不存在：{source}")
        if source.suffix.lower() not in {".pptx", ".pptm"}:
            raise WorkflowError("仅支持 .pptx / .pptm 参考文件。")

        run_id = induction_id or uuid4()
        workspace = Path(self.workspace_root(run_id))
        workspace.mkdir(parents=True, exist_ok=True)
        stored = workspace / "source.pptx"
        shutil.copy2(source, stored)

        tools_ok = screenshot_tools_available()
        presentation = self._parser.parse(
            stored,
            workspace_dir=workspace,
            name=name or source.stem,
            capture_screenshots=capture_screenshots,
        )
        # Ensure slide_count matches PPTX slides even if some pages failed soft.
        presentation.slide_count = len(presentation.slides)

        screenshot_count = self._count_slide_screenshots(workspace, presentation)
        if capture_screenshots:
            presentation.warnings.extend(
                self._screenshot_gap_warnings(
                    presentation,
                    workspace=workspace,
                    tools_available=tools_ok,
                    screenshot_count=screenshot_count,
                )
            )
        if require_screenshots:
            self._require_complete_screenshots(
                presentation,
                workspace=workspace,
                tools_available=tools_ok,
                screenshot_count=screenshot_count,
            )

        classifications = self._classifier.classify_all(presentation.slides)
        clusters = self._clusterer.cluster(presentation.slides, classifications)
        clusters, scores = self._selector.select_for_clusters(clusters, presentation.slides)

        low_confidence = [
            c.slide_id for c in classifications if c.needs_review or c.confidence < 0.55
        ]
        induction = TemplateInductionResult(
            id=run_id,
            name=presentation.name,
            workspace_relative=f"template-induction/{run_id}",
            source_filename=source.name,
            slide_count=presentation.slide_count,
            status=TemplateInductionStatus.REVIEW
            if low_confidence
            else TemplateInductionStatus.DRAFT,
            classifications=classifications,
            clusters=clusters,
            representative_scores=scores,
            warnings=list(presentation.warnings),
            low_confidence_slide_ids=low_confidence,
        )

        artifact_paths = self.export_artifacts(workspace, presentation, induction)
        self._assert_no_absolute_paths(workspace)
        return TemplateInductionRunResult(
            induction=induction,
            presentation=presentation,
            workspace=workspace,
            artifact_paths=artifact_paths,
            screenshot_count=screenshot_count,
            screenshot_tools_available=tools_ok,
        )

    @staticmethod
    def _count_slide_screenshots(
        workspace: Path, presentation: ReferencePresentation
    ) -> int:
        count = 0
        for slide in presentation.slides:
            if not slide.image_path:
                continue
            if (workspace / slide.image_path).is_file():
                count += 1
        return count

    @staticmethod
    def _screenshot_gap_warnings(
        presentation: ReferencePresentation,
        *,
        workspace: Path,
        tools_available: bool,
        screenshot_count: int,
    ) -> list[str]:
        warnings: list[str] = []
        if not tools_available:
            warnings.append(
                "截图工具不可用（需 LibreOffice+pdftoppm 或 Windows PowerPoint）；"
                "页面 PNG 未生成，Review UI 将无预览图。"
            )
            return warnings
        missing = [
            slide.slide_id
            for slide in presentation.slides
            if not slide.image_path or not (workspace / slide.image_path).is_file()
        ]
        if missing:
            warnings.append(
                f"截图工具可用但缺失 {len(missing)}/{len(presentation.slides)} 页 PNG："
                + ", ".join(missing[:8])
            )
        elif screenshot_count != presentation.slide_count:
            warnings.append(
                f"截图数量与页数不一致：png={screenshot_count} slides={presentation.slide_count}"
            )
        return warnings

    @staticmethod
    def _require_complete_screenshots(
        presentation: ReferencePresentation,
        *,
        workspace: Path,
        tools_available: bool,
        screenshot_count: int,
    ) -> None:
        if not tools_available:
            raise WorkflowError(
                "require_screenshots=True 但截图工具不可用"
                "（需要 LibreOffice+pdftoppm 或 Windows PowerPoint）。"
            )
        missing = [
            slide.slide_id
            for slide in presentation.slides
            if not slide.image_path or not (workspace / slide.image_path).is_file()
        ]
        if missing:
            raise WorkflowError(
                "页面截图不完整，无法满足验收："
                + ", ".join(missing[:12])
            )
        if screenshot_count != presentation.slide_count:
            raise WorkflowError(
                f"截图数量与页数不一致：png={screenshot_count} slides={presentation.slide_count}"
            )

    def apply_overrides(
        self,
        induction: TemplateInductionResult,
        presentation: ReferencePresentation,
        overrides: list[InductionReviewOverride],
    ) -> TemplateInductionResult:
        """Apply human corrections (type / cluster / representative) — not numeric scores."""
        class_by_id = {c.slide_id: c for c in induction.classifications}
        for override in overrides:
            clf = class_by_id.get(override.slide_id)
            if clf is None:
                continue
            if override.functional_type is not None:
                clf.functional_type = override.functional_type
                clf.needs_review = False
                clf.evidence = [*clf.evidence, "human override: functional_type"]
            if override.content_type is not None:
                clf.content_type = override.content_type
                clf.evidence = [*clf.evidence, "human override: content_type"]
            if override.is_representative and override.cluster_id:
                for cluster in induction.clusters:
                    if cluster.id == override.cluster_id:
                        cluster.representative_slide_id = override.slide_id
                        cluster.selection_rationale = [
                            "human selected representative",
                            *( [override.notes] if override.notes else [] ),
                        ]
        induction.overrides = list(overrides)
        induction.classifications = list(class_by_id.values())
        # Re-cluster content pages after functional overrides when needed.
        clusters = self._clusterer.cluster(presentation.slides, induction.classifications)
        clusters, scores = self._selector.select_for_clusters(clusters, presentation.slides)
        # Preserve human representative picks.
        for override in overrides:
            if override.is_representative and override.cluster_id:
                for cluster in clusters:
                    if cluster.id == override.cluster_id or override.slide_id in cluster.slide_ids:
                        cluster.representative_slide_id = override.slide_id
        induction.clusters = clusters
        induction.representative_scores = scores
        induction.low_confidence_slide_ids = [
            c.slide_id for c in induction.classifications if c.needs_review
        ]
        induction.status = (
            TemplateInductionStatus.REVIEW
            if induction.low_confidence_slide_ids
            else TemplateInductionStatus.READY
        )
        induction.touch()
        return induction

    def export_artifacts(
        self,
        workspace: Path,
        presentation: ReferencePresentation,
        induction: TemplateInductionResult,
    ) -> dict[str, Path]:
        slides_dir = workspace / "slides"
        slides_dir.mkdir(parents=True, exist_ok=True)

        # Per-slide JSON (+ ensure PNG placeholder note if missing).
        for slide in presentation.slides:
            slide_json = slides_dir / f"{slide.slide_id}.json"
            slide_json.write_text(
                json.dumps(slide.model_dump(mode="json"), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            # If screenshot missing, leave image_path empty (already); do not invent absolute paths.

        ref_path = workspace / "reference_presentation.json"
        ref_path.write_text(
            json.dumps(presentation.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        functional_path = workspace / "functional_classification.json"
        functional_path.write_text(
            json.dumps(
                [c.model_dump(mode="json") for c in induction.classifications],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        clusters_path = workspace / "content_clusters.json"
        clusters_path.write_text(
            json.dumps(
                [c.model_dump(mode="json") for c in induction.clusters],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        reps = []
        for cluster in induction.clusters:
            reps.append(
                {
                    "cluster_id": cluster.id,
                    "representative_slide_id": cluster.representative_slide_id,
                    "functional_type": cluster.functional_type.value,
                    "content_type": cluster.content_type.value,
                    "slide_ids": cluster.slide_ids,
                    "selection_rationale": cluster.selection_rationale,
                    "confidence": cluster.confidence,
                }
            )
        reps_path = workspace / "representative_slides.json"
        reps_path.write_text(
            json.dumps(reps, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        induction_path = workspace / "induction_result.json"
        induction_path.write_text(
            json.dumps(induction.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        return {
            "reference_presentation": ref_path,
            "functional_classification": functional_path,
            "content_clusters": clusters_path,
            "representative_slides": reps_path,
            "induction_result": induction_path,
            "slides_dir": slides_dir,
        }

    def load_workspace(self, workspace: Path) -> tuple[ReferencePresentation, TemplateInductionResult]:
        presentation = ReferencePresentation.model_validate(
            json.loads((workspace / "reference_presentation.json").read_text(encoding="utf-8"))
        )
        induction = TemplateInductionResult.model_validate(
            json.loads((workspace / "induction_result.json").read_text(encoding="utf-8"))
        )
        return presentation, induction

    def content_cluster_count(self, induction: TemplateInductionResult) -> int:
        return sum(
            1
            for c in induction.clusters
            if c.functional_type.value == "content" and len(c.slide_ids) >= 1
        )

    def _assert_no_absolute_paths(self, workspace: Path) -> None:
        for path in workspace.rglob("*.json"):
            text = path.read_text(encoding="utf-8")
            data = json.loads(text)
            self._walk_forbid_absolute(data, context=str(path.relative_to(workspace)))

    def _walk_forbid_absolute(self, node: object, *, context: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key in {"image_path", "relative_path", "source_pptx_relative", "workspace_relative"}:
                    if isinstance(value, str) and is_machine_absolute_path(value):
                        raise WorkflowError(
                            f"绝对路径不得持久化：{context}::{key}={value}"
                        )
                self._walk_forbid_absolute(value, context=context)
        elif isinstance(node, list):
            for item in node:
                self._walk_forbid_absolute(item, context=context)
