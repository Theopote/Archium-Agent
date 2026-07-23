# Workflow route availability

Archium routes presentation jobs by preservation contract before any workflow
side effects occur. Route availability is deliberately separate from the route
contract: having a contract does not mean the implementation is complete.

| Route | Status | Registered handler | Boundary |
| --- | --- | --- | --- |
| Generate from project | Available | `presentation_workflow` | May rebuild content and layout |
| Fill native template | Partial | `reference_slide_editing` | Structured master/layout *emission* exists; in-place preservation of a source template's OOXML masters is not complete |
| Beautify existing deck | Planned | - | No deck-wide wording/order preservation workflow yet |
| Enhance native deck | Planned | - | Notes, transition and timing package editing is not implemented |
| Recover image deck | Available | `slide_recovery_workflow` | Reconstructs editable scene state from visual pages |
| Distill template | Available | `template_induction` | Produces reusable Archium template contracts |

`PresentationWorkflowRouter` is the execution boundary. The composition root
injects one application-service handler per implemented route; the router never
falls back to the generation pipeline. A missing handler fails before side
effects begin. Static availability remains the product-facing declaration, so
partial and planned implementations are not advertised as complete merely
because an experimental handler can be injected in a test or internal tool.

For routes with preservation promises, the composition root must also provide
a route-specific snapshotter. The router takes a baseline before dispatch and
compares the handler result afterwards. Every field in `preserved` must exist
in both snapshots and remain equal. Missing snapshots, missing fields, or
changed values raise `WorkflowError`; in particular, Beautify and Enhance are
fail-closed rather than relying on descriptive metadata.
