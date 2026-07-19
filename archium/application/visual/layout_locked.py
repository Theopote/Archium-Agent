"""Preserve user-locked layout elements across replan and candidate generation."""

from __future__ import annotations

from archium.domain.visual.layout import LayoutElement, LayoutPlan


def locked_elements_from_plan(plan: LayoutPlan | None) -> dict[str, LayoutElement]:
    """Return locked elements keyed by element id."""
    if plan is None:
        return {}
    return {element.id: element for element in plan.elements if element.locked}


def preserve_locked_elements(
    new_plan: LayoutPlan,
    previous_plan: LayoutPlan | None,
) -> LayoutPlan:
    """Overlay locked elements from a previous plan onto a freshly generated plan."""
    locked = locked_elements_from_plan(previous_plan)
    if not locked:
        return new_plan

    merged: list[LayoutElement] = []
    preserved_ids: set[str] = set()
    for element in new_plan.elements:
        previous = locked.get(element.id)
        if previous is not None:
            merged.append(previous.model_copy())
            preserved_ids.add(previous.id)
            continue
        merged.append(element)

    for element_id, element in locked.items():
        if element_id not in preserved_ids:
            merged.append(element.model_copy())

    hero_id = new_plan.hero_element_id
    if hero_id is not None and hero_id not in {element.id for element in merged}:
        locked_hero = locked.get(hero_id)
        if locked_hero is not None:
            hero_id = locked_hero.id

    reading_order = list(new_plan.reading_order)
    for element_id in locked:
        if element_id not in reading_order:
            reading_order.append(element_id)

    return new_plan.model_copy(
        update={
            "elements": merged,
            "hero_element_id": hero_id,
            "reading_order": reading_order,
            "version": new_plan.version + 1,
        }
    )
