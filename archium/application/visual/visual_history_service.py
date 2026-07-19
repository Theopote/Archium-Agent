"""Revision history for per-slide visual intent + layout plan state."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from archium.application.revision_service import RevisionService
from archium.domain.enums import RevisionEntityType, RevisionSource
from archium.domain.revision import EntityRevision
from archium.domain.slide import SlideSpec
from archium.domain.visual.layout import LayoutPlan
from archium.domain.visual.visual_intent import VisualIntent

VISUAL_STATE_SNAPSHOT_KIND = "slide_visual_state"


class VisualHistoryService:
    """Record and restore combined VisualIntent + LayoutPlan snapshots."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._revisions = RevisionService(session)

    def record_state(
        self,
        *,
        slide: SlideSpec,
        visual_intent: VisualIntent | None,
        layout_plan: LayoutPlan | None,
        change_source: RevisionSource,
        note: str | None = None,
    ) -> EntityRevision:
        snapshot = self._build_snapshot(
            slide=slide,
            visual_intent=visual_intent,
            layout_plan=layout_plan,
        )
        return self._revisions.record(
            entity_type=RevisionEntityType.VISUAL_INTENT,
            entity_id=visual_intent.id if visual_intent is not None else None,
            lineage_id=slide.lineage_id,
            presentation_id=slide.presentation_id,
            change_source=change_source,
            snapshot=snapshot,
            note=note,
        )

    def list_slide_visual_revisions(self, slide: SlideSpec) -> list[EntityRevision]:
        revisions = self._revisions.list_by_lineage(slide.lineage_id)
        return [
            revision
            for revision in revisions
            if revision.snapshot.get("kind") == VISUAL_STATE_SNAPSHOT_KIND
        ]

    def restore_at_revision(
        self,
        slide_id: UUID,
        revision_id: UUID,
        *,
        intents: object,
        plans: object,
        presentations: object,
    ) -> tuple[VisualIntent | None, LayoutPlan | None]:
        revision = self._revisions.get_revision(revision_id)
        if revision is None:
            raise ValueError(f"Revision {revision_id} not found")
        snapshot = revision.snapshot
        if snapshot.get("kind") != VISUAL_STATE_SNAPSHOT_KIND:
            raise ValueError("Revision is not a slide visual state snapshot")
        if str(snapshot.get("slide_id")) != str(slide_id):
            raise ValueError("Revision does not belong to the requested slide")
        return self.restore_revision(
            revision,
            intents=intents,
            plans=plans,
            presentations=presentations,
        )

    def latest_restorable_revision(
        self,
        slide: SlideSpec,
        *,
        visual_intent: VisualIntent | None = None,
        layout_plan: LayoutPlan | None = None,
    ) -> EntityRevision | None:
        revisions = self.list_slide_visual_revisions(slide)
        if not revisions:
            return None
        current = self._build_snapshot(
            slide=slide,
            visual_intent=visual_intent,
            layout_plan=layout_plan,
        )
        for index, revision in enumerate(revisions):
            if self._visual_snapshot_matches(revision.snapshot, current):
                next_index = index + 1
                return revisions[next_index] if next_index < len(revisions) else None
        return revisions[0]

    def restore_revision(
        self,
        revision: EntityRevision,
        *,
        intents: object,
        plans: object,
        presentations: object,
    ) -> tuple[VisualIntent | None, LayoutPlan | None]:
        snapshot = revision.snapshot
        if snapshot.get("kind") != VISUAL_STATE_SNAPSHOT_KIND:
            raise ValueError("Revision is not a slide visual state snapshot")

        intent_data = snapshot.get("visual_intent")
        plan_data = snapshot.get("layout_plan")
        intent = VisualIntent.model_validate(intent_data) if intent_data else None
        plan = LayoutPlan.model_validate(plan_data) if plan_data else None

        slide_id = UUID(str(snapshot["slide_id"]))
        slide = presentations.get_slide(slide_id)  # type: ignore[attr-defined]
        if slide is None:
            raise ValueError(f"Slide {slide_id} not found")

        if intent is not None:
            intent = intents.save(intent)  # type: ignore[attr-defined]
            slide.visual_intent_id = intent.id
        if plan is not None:
            plan = plans.save(plan)  # type: ignore[attr-defined]
            slide.layout_plan_id = plan.id
        presentations.save_slide(slide)  # type: ignore[attr-defined]
        return intent, plan

    @staticmethod
    def _visual_snapshot_matches(stored: dict[str, object], current: dict[str, object]) -> bool:
        return (
            stored.get("visual_intent") == current.get("visual_intent")
            and stored.get("layout_plan") == current.get("layout_plan")
        )

    @staticmethod
    def _build_snapshot(
        *,
        slide: SlideSpec,
        visual_intent: VisualIntent | None,
        layout_plan: LayoutPlan | None,
    ) -> dict[str, object]:
        return {
            "kind": VISUAL_STATE_SNAPSHOT_KIND,
            "slide_id": str(slide.id),
            "slide_visual_intent_id": (
                str(slide.visual_intent_id) if slide.visual_intent_id is not None else None
            ),
            "slide_layout_plan_id": (
                str(slide.layout_plan_id) if slide.layout_plan_id is not None else None
            ),
            "visual_intent": (
                visual_intent.model_dump(mode="json") if visual_intent is not None else None
            ),
            "layout_plan": (
                layout_plan.model_dump(mode="json") if layout_plan is not None else None
            ),
        }
