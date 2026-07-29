Session: 2026-07-29-pilot-trio-rerender

Purpose: Re-render pilot trio after asset presentation readiness hardening.

Round 1 (morning): readiness gates + layout fixes; human r1 found stub assets / broken perception.
Round 2 (afternoon): refresh_pilot_trio_curated_assets + stub detection + PPTX media gate.

Cases:
- case_001_site_plan
- case_002_site_photos
- case_006_project_hero

Commands:
  py -3 scripts/refresh_pilot_trio_curated_assets.py
  py -3 scripts/render_architectural_benchmark_visuals.py --approve-goldens \
    --case case_001_site_plan --case case_002_site_photos --case case_006_project_hero
  py -3 scripts/check_pilot_trio_acceptance.py

Final status (r2):
- Automation: 3/3 ready_with_minor_edits
- Human review: 3/3 fixable (target met)
- render_valid=true, placeholder_asset_count=0, pptx_screenshot_generated=true

Engineering changes:
- archium/application/asset_presentation_readiness_service.py: tighter stub detection
- tests/benchmark/.../curated_assets.py: provenance via presentation_ready
- tests/benchmark/.../render_pipeline.py: PPTX embedded media gate
- scripts/refresh_pilot_trio_curated_assets.py: pilot fixture PNG generator

Next: replace fixture PNGs with real project assets for formal delivery sign-off.
