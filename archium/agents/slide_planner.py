"""Compatibility shim — SlidePlanService lives under application.narrative.

Prefer::

    from archium.application.narrative import SlidePlanService
"""

from __future__ import annotations

from archium.application.narrative.slide_plan_service import SlidePlanService as SlidePlanner

__all__ = ["SlidePlanner"]
