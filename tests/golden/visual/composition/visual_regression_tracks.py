"""Visual regression tracks: preview (wireframe) vs pptx (final deliverable).

Archium must not conflate:

  preview_visual_regression
    LayoutPlan → Python wireframe ``preview.png``
    Gates geometry boxes only.

  pptx_visual_regression
    LayoutPlan → PptxGenJS → PPTX → LibreOffice/PowerPoint → ``pptx_screenshot.png``
    Gates final deliverable appearance.

Baseline updates require human review:

  generate candidates → CI artifact → manual review → ``approve-baseline``
"""

from __future__ import annotations

# Env for writing *candidates* only (never silent baseline overwrite).
CANDIDATE_ENV = "ARCHIUM_WRITE_PPTX_SCREENSHOT_CANDIDATES"
# Legacy env — still accepted but only writes candidates; approve is separate.
LEGACY_UPDATE_ENV = "UPDATE_LAYOUT_PPTX_SCREENSHOT_GOLDENS"

PREVIEW_MARKER = "preview_visual_regression"
PPTX_MARKER = "pptx_visual_regression"
# Back-compat alias still registered in pytest.
PPTX_MARKER_LEGACY = "layout_pptx_screenshot"

CANDIDATE_DIRNAME = "candidates"
CANDIDATE_SCREENSHOT_NAME = "pptx_screenshot.candidate.png"
CANDIDATE_MANIFEST_NAME = "pptx_screenshot_manifest.candidate.json"
