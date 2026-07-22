# PowerPoint capability and workflow contract

Archium treats `RenderScene` as the canonical presentation scene language and the complete
source of visible slide content. PPTX is a derived delivery artifact, not an independent
authoring source.

## RenderScene closure invariant

Every visible object emitted by a renderer must trace to exactly one visible `RenderScene`
node. A renderer may transform coordinates, map object types, substitute fonts, bind declared
masters/layouts, package sidecars, or perform an explicitly disclosed safe degradation. It may
not invent titles, icons, decoration, assets, or wording. Missing, extra, or duplicate emissions
are contract violations.

The executable check lives in `PowerPointContractService.validate_scene_closure`. Renderer
adapters should report `RendererEmission` records and call `require_scene_closure` before the
delivery artifact is accepted.

## V1 capability mapping

| Scene node | PowerPoint object | Fidelity | Important boundary |
| --- | --- | --- | --- |
| text | `p:sp` + `p:txBody` | native stable | font substitution can change wrapping |
| shape | `p:sp` | native normalized | only rectangle, ellipse, line, card |
| image | `p:pic` | native stable | pixels remain raster |
| drawing | `p:pic` | native stable | drawing is not native CAD/vector geometry in V1 |

Unknown node types fail closed. Fidelity is deliberately more precise than deck-level labels
such as “fully editable”: it describes the actual PowerPoint representation of each construct.

## Workflow routes

Generation, native template fill, beautification, native enhancement, image-deck recovery, and
template distillation have separate preservation contracts in `workflow_route.py`. In particular,
beautification preserves page count, order, wording, and citations; template fill preserves the
declared master/layout/placeholder/theme structure; native enhancement may change only notes,
narration, transitions, and timing.

## Current boundary

Archium already extracts master/layout metadata and durable placeholder bindings. Structured
master/layout generation is not yet claimed: it requires explicit template declarations plus
OOXML relationship validation. Canonical SVG may be explored as a renderer backend, but it must
not replace `RenderScene` as authored state.

Design ideas were informed by the MIT-licensed `hugohe3/ppt-master` project; this implementation
uses Archium's own domain model and contains no copied converter code.
