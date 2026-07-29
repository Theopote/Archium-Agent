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
- case_002_site_photos → suggested=needs_review (TEXT_OVERFLOW on title/annotations)
- case_006_project_hero → suggested=needs_review (TEXT_OVERFLOW on lead; hero_ratio=0.752)

What this is NOT:
- Human exception review (reporting_ready not updated)
- Delivery acceptance / ready_with_minor_edits sign-off

Next:
- Settings → 建筑幻灯片基准 · 人工视觉评审 (pilot trio only)
- Update reporting_ready if pages reach ready_with_minor_edits
