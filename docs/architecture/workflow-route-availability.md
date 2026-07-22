# Workflow route availability

Archium routes presentation jobs by preservation contract before any workflow
side effects occur. Route availability is deliberately separate from the route
contract: having a contract does not mean the implementation is complete.

| Route | Status | Registered handler | Boundary |
| --- | --- | --- | --- |
| Generate from project | Available | `presentation_workflow` | May rebuild content and layout |
| Fill native template | Partial | `reference_slide_editing` | Produces RenderScene; native OOXML master preservation is not complete |
| Beautify existing deck | Planned | - | No deck-wide wording/order preservation workflow yet |
| Enhance native deck | Planned | - | Notes, transition and timing package editing is not implemented |
| Recover image deck | Available | `slide_recovery_workflow` | Reconstructs editable scene state from visual pages |
| Distill template | Available | `template_induction` | Produces reusable Archium template contracts |

Callers should resolve the route registration and required inputs before
constructing a handler. Partial or planned routes fail with their declared
limitations instead of silently falling back to the generation pipeline.
