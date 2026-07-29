Session: 2026-07-29-pilot-trio-rerender

Purpose: Re-render pilot trio after asset presentation readiness hardening (pixel_analyzed gate).

Cases:
- case_001_site_plan
- case_002_site_photos
- case_006_project_hero

Command:
  py -3 scripts/render_architectural_benchmark_visuals.py --approve-goldens \
    --case case_001_site_plan \
    --case case_002_site_photos \
    --case case_006_project_hero

Automation evidence (per render_manifest.json):
- pptx_screenshot_generated=true
- pptx_screenshot_reused=false
- render_valid=true
- post_render_qa_passed=true
- placeholder_asset_count=0 (all three cases)

Automation pre-check (scripts/check_pilot_trio_acceptance.py):
- case_001_site_plan → suggested=ready_with_minor_edits (layout_valid, hero_ratio=0.722)
- case_002_site_photos → suggested=ready_with_minor_edits (hierarchical, primary larger)
- case_006_project_hero → suggested=ready_with_minor_edits (hero_ratio=0.706)

Human exception review (2026-07-29, desk-review-2026-07-29):
- case_001_site_plan → fixable (layout OK; replace real site plan drawing)
- case_002_site_photos → fixable (hierarchical OK; replace real site photos)
- case_006_project_hero → do_not_use (PPTX hero still not dominant)

Target ready_with_minor_edits: NOT fully met (2/3 fixable, 1/3 do_not_use).

Open blockers:
- Curated benchmark assets are filename-grid / solid-color bars, not real content
- pptx_render.png shows broken image icons (benchmark:// embed failure in PowerPoint COM)
- pixel_acceptable threshold too low for curated pool assets

Next:
- Replace curated pool assets with real drawings/photos for pilot trio
- Fix PPTX image embed for benchmark:// URIs
- Re-run render + human review before expanding to 30 pages
