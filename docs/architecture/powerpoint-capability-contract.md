# PowerPoint capability and workflow contract

Archium treats `RenderScene` as the canonical presentation scene language and the complete
source of visible slide content. PPTX is a derived delivery artifact, not an independent
authoring source.

## RenderScene closure invariant

Every emitted object must have a unique `emission_id` and trace to a visible `RenderScene`
node. Every visible node must produce at least one emission. A renderer may transform
coordinates, map object types, substitute fonts, bind declared
masters/layouts, package sidecars, or perform an explicitly disclosed safe degradation. It may
not invent titles, icons, decoration, assets, or wording.

The capability mapping declares `one_to_one`, `one_to_many`, or `many_to_one` cardinality.
Multiple objects from one node are valid only for a declared `one_to_many` mapping, and each
must carry a role and unique sequence. Duplicate emission identities, missing source nodes,
untraceable emissions, and cardinality violations are contract failures. `many_to_one` is
reserved but intentionally rejected by the V1 single-source emission schema.

The executable check lives in `PowerPointContractService.validate_scene_closure`. Renderer
adapters should report `RendererEmission` records and call `require_scene_closure` before the
delivery artifact is accepted.

## V1 capability mapping

| Scene node | PowerPoint object | Fidelity | Important boundary |
| --- | --- | --- | --- |
| text | `p:sp` + `p:txBody` | native stable | font substitution can change wrapping |
| shape | `p:sp` | feature-dependent | simple rectangle is stable; other V1 shapes currently normalize to rectangle |
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

Archium extracts master/layout metadata and durable placeholder bindings, and can
**emit** structured PPTX packages when `PptxStructureMode.STRUCTURED` is selected:

- Domain specs: `SlideMasterSpec`, `SlideLayoutSpec`, `PlaceholderSpec`
- PptxGenJS defines multiple named layouts with placeholders
- A post-export expander clones masters so each `SlideMasterSpec` is a real
  `ppt/slideMasters/slideMasterN.xml` part (PptxGenJS alone collapses to one master)
- OOXML validation reads `presentation.xml`, `ppt/slideMasters/`,
  `ppt/slideLayouts/`, and `ppt/slides/_rels/` (Slide → Layout → Master)

Default export remains `FLAT` (absolute freeform shapes) for backward compatibility.
Set `PPTX_STRUCTURE_MODE=structured` or pass `structure_mode=STRUCTURED` on
`PptxRenderer` / deck adapters to opt in.

`FILL_NATIVE_TEMPLATE` remains Partial: structured *generation* is available, but
filling an existing enterprise template while preserving that file's original
OOXML master/layout identities in place is not yet complete.

Canonical SVG may be explored as a renderer backend, but it must not replace
`RenderScene` as authored state.

Design ideas were informed by the MIT-licensed `hugohe3/ppt-master` project; this
implementation uses Archium's own domain model and contains no copied converter
code.
