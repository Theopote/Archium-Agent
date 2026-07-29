## Summary

<!-- What does this PR change, and why? -->

## Test plan

- [ ] Relevant unit / integration tests pass locally
- [ ] If UI changed: manually smoke-tested Streamlit flow
- [ ] If workflow / Mission / export changed: ran related golden or smoke tests
- [ ] Docs updated when user-facing behavior changed
- [ ] No secrets, `.env`, or unredacted client files included

## Visual Change PR Gate

**Required when this PR touches any of:**

- `archium/domain/visual/**`
- `archium/infrastructure/renderers/**`
- `archium/infrastructure/layout/**` (generators / solver / tokens)
- `archium/ui/studio/**` or Studio canvas editor
- `tests/benchmark/**` goldens or curated baselines
- `tests/golden/visual/**` screenshot / composition baselines

If none of the above apply, write `N/A` under each item and skip the checklist.

### Checklist

- [ ] **Before / After** collage attached (key pages; PNG or CI artifact links)
- [ ] **PPTX screenshot(s)** attached or linked from CI `layout-pptx-screenshot` / benchmark artifacts
- [ ] **Affected `LayoutFamily` / variants** listed below
- [ ] **Golden impact** declared (see options)
- [ ] **Human revision cost** estimated (see options)
- [ ] CI green for visual-required checks (see `docs/branch-protection.md`)

### Affected layout families

<!-- e.g. HERO/full_bleed, EVIDENCE_BOARD/hierarchical, DRAWING_FOCUS/drawing_with_metrics -->

-

### Golden / baseline impact

- [ ] No golden / screenshot baseline changes
- [ ] Golden / baseline updated intentionally — describe why and approval path
- [ ] New golden / case added

### Human revision cost

- [ ] None expected (automated gates sufficient)
- [ ] Low — spot-check 1–3 pages in Studio
- [ ] Medium — full pilot page set / human visual review JSON
- [ ] High — real-project acceptance or baseline re-approval needed

## Notes

<!-- Breaking changes, follow-ups, non-visual screenshots -->
