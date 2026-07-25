"""Compatibility shim — citation helpers live under application.

Prefer::

    from archium.application.citation_resolution import (
        citation_from_draft,
        enrich_slide_citations,
    )
"""

from __future__ import annotations

from archium.application.citation_resolution import (
    citation_from_draft,
    enrich_slide_citations,
)

__all__ = ["citation_from_draft", "enrich_slide_citations"]
