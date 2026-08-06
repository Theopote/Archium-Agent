"""Automatic migration tool for VisualIntent to v0.3 architecture.

Infers page_type and composition_strategy from existing VisualIntent data
to enable gradual migration to the new PageType + CompositionStrategy architecture.
"""

from __future__ import annotations

from uuid import UUID

from archium.application.unit_of_work import SessionLike, session_of
from archium.domain.visual.composition_strategy import (
    CompositionAxis,
    CompositionStrategy,
    ImageRole,
    ReadingPathType,
    TypographyRole,
    VisualBalance,
    VisualTension,
    WhiteSpaceStrategy,
    suggest_strategy_for_content,
)
from archium.domain.visual.enums import LayoutFamily, VisualContentType
from archium.domain.visual.page_type import (
    PageType,
    infer_page_type_from_layout_family,
    suggest_page_type_from_content,
)
from archium.domain.visual.visual_intent import VisualIntent
from archium.infrastructure.database.visual_repositories import VisualIntentRepository
from archium.logging import get_logger

logger = get_logger(__name__, operation="visual_intent_migration")


class VisualIntentMigrationService:
    """Migrate existing VisualIntent records to v0.3 architecture."""

    def __init__(self, session: SessionLike) -> None:
        self._session = session_of(session)
        self._intents = VisualIntentRepository(self._session)

    def migrate_intent(
        self,
        intent: VisualIntent,
        *,
        overwrite_existing: bool = False,
    ) -> VisualIntent:
        """Infer and populate page_type and composition_strategy for a VisualIntent.

        Args:
            intent: VisualIntent to migrate
            overwrite_existing: If False, skip if already has structured composition

        Returns:
            Updated VisualIntent (not saved, caller must save)
        """
        # Skip if already migrated (unless overwrite)
        if not overwrite_existing and intent.page_type and intent.has_structured_composition():
            logger.debug(
                f"VisualIntent {intent.id} already migrated, skipping",
                extra={"intent_id": str(intent.id)},
            )
            return intent

        # Infer page_type
        page_type = self._infer_page_type(intent)

        # Infer composition_strategy
        composition_strategy = self._infer_composition_strategy(intent)

        # Update intent
        updated = intent.model_copy(
            update={
                "page_type": page_type,
                "composition_strategy": composition_strategy,
            }
        )

        logger.info(
            f"Migrated VisualIntent {intent.id}: page_type={page_type}, "
            f"composition={composition_strategy.archetype if isinstance(composition_strategy, CompositionStrategy) else 'legacy'}",
            extra={
                "intent_id": str(intent.id),
                "page_type": page_type.value if page_type else None,
                "has_structured_composition": isinstance(composition_strategy, CompositionStrategy),
            },
        )

        return updated

    def _infer_page_type(self, intent: VisualIntent) -> PageType | None:
        """Infer PageType from existing VisualIntent data."""
        # 1. Try preferred_layout_families
        if intent.preferred_layout_families:
            return infer_page_type_from_layout_family(intent.preferred_layout_families[0].value)

        # 2. Try dominant_content_type
        content_type_map = {
            VisualContentType.HERO_IMAGE: PageType.COVER,
            VisualContentType.SITE_PLAN: PageType.SITE_ANALYSIS,
            VisualContentType.FLOOR_PLAN: PageType.TECHNICAL_DRAWING,
            VisualContentType.SECTION: PageType.TECHNICAL_DRAWING,
            VisualContentType.ELEVATION: PageType.TECHNICAL_DRAWING,
            VisualContentType.PHOTO_EVIDENCE: PageType.EVIDENCE,
            VisualContentType.ANALYTICAL_DIAGRAM: PageType.SPATIAL_ANALYSIS,
            VisualContentType.COMPARISON: PageType.COMPARISON,
            VisualContentType.METRICS: PageType.DATA_METRICS,
            VisualContentType.TEXT_ARGUMENT: PageType.TEXT_ARGUMENT,
            VisualContentType.PROCESS: PageType.PROCESS,
        }
        if intent.dominant_content_type in content_type_map:
            return content_type_map[intent.dominant_content_type]

        # 3. Try heuristic analysis
        has_site_map = intent.dominant_content_type == VisualContentType.SITE_PLAN
        has_technical_drawing = intent.dominant_content_type in {
            VisualContentType.FLOOR_PLAN,
            VisualContentType.SECTION,
            VisualContentType.ELEVATION,
        }
        has_data_chart = intent.dominant_content_type == VisualContentType.METRICS
        has_comparison = intent.dominant_content_type == VisualContentType.COMPARISON
        has_timeline = intent.dominant_content_type == VisualContentType.PROCESS
        text_is_argumentative = intent.dominant_content_type == VisualContentType.TEXT_ARGUMENT

        return suggest_page_type_from_content(
            has_site_map=has_site_map,
            has_technical_drawing=has_technical_drawing,
            has_data_chart=has_data_chart,
            has_comparison_structure=has_comparison,
            has_timeline=has_timeline,
            text_is_argumentative=text_is_argumentative,
            is_opening_slide=False,
        )

    def _infer_composition_strategy(
        self, intent: VisualIntent
    ) -> CompositionStrategy | str | None:
        """Infer CompositionStrategy from existing VisualIntent data."""
        # If already has string composition_strategy, keep it
        if isinstance(intent.composition_strategy, str) and intent.composition_strategy:
            return intent.composition_strategy

        # Analyze content to suggest archetype
        has_large_image = intent.hero_asset_id is not None
        has_technical_drawing = intent.dominant_content_type in {
            VisualContentType.SITE_PLAN,
            VisualContentType.FLOOR_PLAN,
            VisualContentType.SECTION,
            VisualContentType.ELEVATION,
        }
        has_data_chart = intent.dominant_content_type == VisualContentType.METRICS
        text_density = self._estimate_text_density(intent)

        archetype = suggest_strategy_for_content(
            has_large_image=has_large_image,
            has_technical_drawing=has_technical_drawing,
            has_data_chart=has_data_chart,
            text_density=text_density,
        )

        # Build CompositionStrategy based on archetype and intent data
        return self._build_composition_strategy(intent, archetype)

    def _estimate_text_density(self, intent: VisualIntent) -> str:
        """Estimate text density from VisualIntent (heuristic)."""
        if intent.dominant_content_type == VisualContentType.TEXT_ARGUMENT:
            return "high"
        if intent.dominant_content_type in {
            VisualContentType.HERO_IMAGE,
            VisualContentType.SITE_PLAN,
        }:
            return "low"
        return "moderate"

    def _build_composition_strategy(
        self, intent: VisualIntent, archetype: str
    ) -> CompositionStrategy:
        """Build CompositionStrategy from archetype and intent data."""
        from archium.domain.visual.composition_strategy import ARCHETYPE_PRESETS

        # Start with preset
        preset = ARCHETYPE_PRESETS.get(archetype)
        if preset:
            # Customize based on intent data
            overrides = {}

            # Adjust based on density_level
            if hasattr(intent, "density_level"):
                from archium.domain.visual.enums import DensityLevel

                if intent.density_level == DensityLevel.SPACIOUS:
                    overrides["white_space"] = WhiteSpaceStrategy.GENEROUS
                elif intent.density_level == DensityLevel.COMPACT:
                    overrides["white_space"] = WhiteSpaceStrategy.COMPACT

            # Adjust based on reading_order
            if intent.reading_order:
                overrides["visual_hierarchy"] = intent.reading_order[:4]

            return preset.model_copy(update=overrides)

        # Fallback: build from scratch
        return CompositionStrategy(
            archetype=archetype,
            dominant_axis=CompositionAxis.HORIZONTAL,
            reading_path=ReadingPathType.Z_PATTERN,
            tension=VisualTension.ASYMMETRIC,
            balance=VisualBalance.LEFT_WEIGHTED,
            image_role=ImageRole.DOMINANT if intent.hero_asset_id else ImageRole.SUPPORTING,
            typography_role=TypographyRole.EDITORIAL,
            white_space=WhiteSpaceStrategy.BALANCED,
        )

    def migrate_all_intents(
        self,
        *,
        overwrite_existing: bool = False,
        dry_run: bool = False,
    ) -> tuple[int, int]:
        """Migrate all VisualIntent records in the database.

        Args:
            overwrite_existing: If False, skip already-migrated intents
            dry_run: If True, don't save changes

        Returns:
            (migrated_count, skipped_count)
        """
        all_intents = self._intents.list_all()
        migrated = 0
        skipped = 0

        for intent in all_intents:
            if not overwrite_existing and intent.page_type and intent.has_structured_composition():
                skipped += 1
                continue

            updated = self.migrate_intent(intent, overwrite_existing=overwrite_existing)

            if not dry_run:
                self._intents.save(updated)

            migrated += 1

        logger.info(
            f"Migration complete: {migrated} migrated, {skipped} skipped (dry_run={dry_run})",
            extra={
                "migrated_count": migrated,
                "skipped_count": skipped,
                "dry_run": dry_run,
            },
        )

        return migrated, skipped

    def migrate_by_presentation(
        self,
        presentation_id: UUID,
        *,
        overwrite_existing: bool = False,
        dry_run: bool = False,
    ) -> tuple[int, int]:
        """Migrate all VisualIntent records for a specific presentation.

        Args:
            presentation_id: Presentation UUID
            overwrite_existing: If False, skip already-migrated intents
            dry_run: If True, don't save changes

        Returns:
            (migrated_count, skipped_count)
        """
        intents = self._intents.list_by_presentation(presentation_id)
        migrated = 0
        skipped = 0

        for intent in intents:
            if not overwrite_existing and intent.page_type and intent.has_structured_composition():
                skipped += 1
                continue

            updated = self.migrate_intent(intent, overwrite_existing=overwrite_existing)

            if not dry_run:
                self._intents.save(updated)

            migrated += 1

        logger.info(
            f"Migration complete for presentation {presentation_id}: "
            f"{migrated} migrated, {skipped} skipped (dry_run={dry_run})",
            extra={
                "presentation_id": str(presentation_id),
                "migrated_count": migrated,
                "skipped_count": skipped,
                "dry_run": dry_run,
            },
        )

        return migrated, skipped
