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

What this is NOT:
- Human exception review (reporting_ready not updated)
- Delivery acceptance / ready_with_minor_edits sign-off

Next:
- Settings → 建筑幻灯片基准 · 人工视觉评审 (pilot trio only)
- Update reporting_ready if pages reach ready_with_minor_edits
