"""Facade for automated four-layer presentation review."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.chunk_models import ProjectContextBundle
from archium.application.review.architectural import ArchitecturalReviewer
from archium.application.review.content import ContentReviewer
from archium.application.review.evidence import EvidenceReviewer
from archium.application.review.layout import LayoutReviewer
from archium.application.review.scene_render_qa import PostRenderReviewer, SceneSemanticReviewer
from archium.application.review.slide_semantic import SlideSemanticReviewer
from archium.config.settings import Settings, get_settings
from archium.domain.presentation import PresentationBrief, Storyline
from archium.domain.reference_style import ReferenceStyleProfile
from archium.domain.renovation_issue import RenovationIssueMap
from archium.domain.review import ReviewIssue
from archium.domain.slide import SlideSpec
from archium.domain.visual.render_scene import RenderScene
from archium.infrastructure.llm.base import LLMProvider


class AutomatedReviewService:
    """Run rule-based and optional LLM-assisted presentation QA checks."""

    def __init__(
        self,
        session: Session,
        *,
        llm: LLMProvider | None = None,
        settings: Settings | None = None,
    ) -> None:
        resolved_settings = settings or get_settings()
        self._content = ContentReviewer(session, llm=llm, settings=resolved_settings)
        self._evidence = EvidenceReviewer(session, llm=llm, settings=resolved_settings)
        self._architectural = ArchitecturalReviewer(session, llm=llm, settings=resolved_settings)
        self._layout = LayoutReviewer(session, llm=llm, settings=resolved_settings)
        self._semantic = SlideSemanticReviewer(session, llm=llm, settings=resolved_settings)
        self._scene_semantic = SceneSemanticReviewer(session, llm=llm, settings=resolved_settings)
        self._post_render = PostRenderReviewer(session, llm=llm, settings=resolved_settings)

    def run_content_review(
        self,
        presentation_id: UUID,
        slides: list[SlideSpec],
        *,
        brief: PresentationBrief | None = None,
    ) -> list[ReviewIssue]:
        return self._content.run(presentation_id, slides, brief=brief)

    def run_evidence_review(
        self,
        presentation_id: UUID,
        slides: list[SlideSpec],
        *,
        context_bundle: ProjectContextBundle | None = None,
    ) -> list[ReviewIssue]:
        return self._evidence.run(presentation_id, slides, context_bundle=context_bundle)

    def run_architectural_review(
        self,
        presentation_id: UUID,
        slides: list[SlideSpec],
        *,
        brief: PresentationBrief | None = None,
        storyline: Storyline | None = None,
    ) -> list[ReviewIssue]:
        return self._architectural.run(
            presentation_id,
            slides,
            brief=brief,
            storyline=storyline,
        )

    def run_layout_review(
        self,
        presentation_id: UUID,
        slides: list[SlideSpec],
        *,
        project_id: UUID | None = None,
        brief: PresentationBrief | None = None,
        storyline: Storyline | None = None,
        context_bundle: ProjectContextBundle | None = None,
        renovation_issue_map: RenovationIssueMap | None = None,
        reference_style_profile: ReferenceStyleProfile | None = None,
    ) -> list[ReviewIssue]:
        issues = self._layout.run(
            presentation_id,
            slides,
            project_id=project_id,
            brief=brief,
            storyline=storyline,
            context_bundle=context_bundle,
        )
        issues.extend(
            self._semantic.run(
                presentation_id,
                slides,
                project_id=project_id,
                brief=brief,
                context_bundle=context_bundle,
                renovation_issue_map=renovation_issue_map,
                reference_style_profile=reference_style_profile,
            )
        )
        return issues

    def run_slide_semantic_review(
        self,
        presentation_id: UUID,
        slides: list[SlideSpec],
        *,
        project_id: UUID | None = None,
        brief: PresentationBrief | None = None,
        context_bundle: ProjectContextBundle | None = None,
        renovation_issue_map: RenovationIssueMap | None = None,
        reference_style_profile: ReferenceStyleProfile | None = None,
    ) -> list[ReviewIssue]:
        return self._semantic.run(
            presentation_id,
            slides,
            project_id=project_id,
            brief=brief,
            context_bundle=context_bundle,
            renovation_issue_map=renovation_issue_map,
            reference_style_profile=reference_style_profile,
        )

    def run_scene_semantic_review(
        self,
        presentation_id: UUID,
        slides: list[SlideSpec],
        scenes: list[RenderScene],
        *,
        project_id: UUID | None = None,
        pptx_paths_by_slide: dict[UUID, Path] | None = None,
    ) -> list[ReviewIssue]:
        return self._scene_semantic.run(
            presentation_id,
            slides,
            scenes,
            project_id=project_id,
            pptx_paths_by_slide=pptx_paths_by_slide,
        )

    def run_post_render_review(
        self,
        presentation_id: UUID,
        slides: list[SlideSpec],
        screenshots: list[tuple[UUID, Path]],
        *,
        project_id: UUID | None = None,
        scenes_by_slide: dict[UUID, RenderScene] | None = None,
        pptx_screenshots: dict[UUID, Path] | None = None,
    ) -> list[ReviewIssue]:
        return self._post_render.run(
            presentation_id,
            slides,
            screenshots,
            project_id=project_id,
            scenes_by_slide=scenes_by_slide,
            pptx_screenshots=pptx_screenshots,
        )

    def run_professional_review(
        self,
        presentation_id: UUID,
        slides: list[SlideSpec],
        *,
        brief: PresentationBrief | None = None,
        storyline: Storyline | None = None,
        context_bundle: ProjectContextBundle | None = None,
        project_id: UUID | None = None,
    ) -> list[ReviewIssue]:
        """Run all four review layers (backward-compatible aggregate entry point)."""
        issues: list[ReviewIssue] = []
        issues.extend(self.run_content_review(presentation_id, slides, brief=brief))
        issues.extend(
            self.run_evidence_review(presentation_id, slides, context_bundle=context_bundle)
        )
        issues.extend(
            self.run_architectural_review(
                presentation_id,
                slides,
                brief=brief,
                storyline=storyline,
            )
        )
        issues.extend(
            self.run_layout_review(
                presentation_id,
                slides,
                project_id=project_id,
                brief=brief,
                storyline=storyline,
                context_bundle=context_bundle,
            )
        )
        return issues

    def summarize_for_slides(self, issues: list[ReviewIssue]) -> list[str]:
        return [f"{issue.title}: {issue.description}" for issue in issues if issue.slide_id]
