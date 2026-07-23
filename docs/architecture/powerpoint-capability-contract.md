# PowerPoint capability and workflow contract

Archium treats `RenderScene` as the canonical presentation scene language and the complete
source of visible slide content. PPTX is a derived delivery artifact, not an independent
authoring source.

**Important:** having a capability *map* is not the same as PowerPoint native *depth*.
Do **not** describe Archium as “深度原生 PowerPoint” / “deep native PowerPoint” / a
PowerPoint-complete object model. That claim is forbidden until the depth inventory
below is substantially implemented (`FORBIDDEN_NATIVE_DEPTH_CLAIMS` /
`native_depth_is_shallow()` in `powerpoint_capability.py`).

## Canonical Presentation Model

| Layer | Answers | Authority |
| --- | --- | --- |
| `SlideSpec` | What does this slide claim? | Content expression SSOT |
| `LayoutPlan` | How is space organized? | Geometry compile (pre–Studio edit) |
| `RenderScene` | Which visual objects exist? | Render / Studio / **formal editable PPTX** |
| `PresentationSpec` | Legacy template execution payload | Derived-only compat; **no new layout logic** |

Formal delivery filename is always `presentation.pptx` (`FORMAL_DELIVERY_PPTX_FILENAME`).
LayoutPlan instruction PPTX is validation-only when enabled
(`presentation.layout_plan.validation.pptx`). See `export_authority.py` and
`docs/architecture/current-system.md` (DOM-003 / RP-002 / RP-003).

`geometry_authority` on `LayoutPlan`: `layout_plan` after engine write; flips to
`render_scene` after Studio/scene repair geometry edits; layout refresh reclaims
`layout_plan` then force-recompiles.

## RenderScene closure invariant

Every emitted object must have a unique `emission_id` and trace to a visible `RenderScene`
node. Every visible node must produce at least one emission. A renderer may transform
coordinates, map object types, substitute fonts, bind declared
masters/layouts, package sidecars, or perform an explicitly disclosed safe degradation. It may
not invent titles, icons, decoration, assets, or wording.

The capability mapping declares `one_to_one`, `one_to_many`, or `many_to_one` cardinality.
Multiple objects from one node are valid for a declared `one_to_many` mapping (each with a
role and unique sequence) — they must **not** be treated as duplicate errors. `many_to_one`
is supported when an emission lists multiple sources via `additional_source_node_ids`.
Duplicate emission identities, missing source nodes, untraceable emissions, and cardinality
violations remain contract failures.

`PowerPointContractService.plan_emissions` expands CROSS_APP_STABLE chart/table bakes into
traceable `one_to_many` emissions (backdrop / bars / labels or header / cell grids). Native
data-backed mode stays `one_to_one` (`c:chart` / `a:tbl`). Renderer adapters and
`PptxRenderer.export_presentation` call `require_scene_closure` before the delivery
artifact is accepted. Export also runs the capability gate (`UNSUPPORTED` /
`BAKE_REQUIRED`) and object-type checks, then records them on the `DeckExportManifest`.

## V1 scene-node capability mapping

| Scene node | PowerPoint object | Fidelity | Important boundary |
| --- | --- | --- | --- |
| text | `p:sp` + `p:txBody` | native stable | font substitution can change wrapping |
| shape | `p:sp` | feature-dependent | rectangle / ellipse / line / card only; others normalize |
| image | `p:pic` | native stable | pixels remain raster; shadow/crop effects approximate |
| drawing | `p:pic` | native stable | drawing is not native CAD/vector geometry in V1 |
| chart | `c:chart` or shape bake | mode-dependent | opt-in dual export; not full chart effect surface |
| table | `a:tbl` or text grid | mode-dependent | opt-in dual export; styling depth limited |

Unknown node types fail closed. Fidelity is deliberately more precise than deck-level labels
such as “fully editable”: it describes the actual PowerPoint representation of each construct
**within the shallow V1 surface**, not ppt-master-class native depth.

## Native depth inventory (honest)

Executable source: `POWERPOINT_NATIVE_DEPTH_INVENTORY` in
`archium/domain/powerpoint_capability.py`.

| Construct | Status |
| --- | --- |
| Text body | Implemented |
| Basic shape (rect/ellipse/line/card) | Partial |
| Picture | Implemented |
| Native Chart + workbook | Partial (opt-in) |
| Native Table | Partial (opt-in) |
| Slide Master / Layout | Partial (STRUCTURED emit) |
| Placeholder | Partial |
| Speaker Notes | Implemented |
| Connector | **Not implemented** |
| Preset Shape library | **Not implemented** |
| Freeform Path | **Not implemented** |
| Group | **Not implemented** |
| Gradient fill | **Not implemented** |
| Pattern fill | **Not implemented** |
| Shadow effect | **Not implemented** |
| Glow effect | **Not implemented** |
| Picture / shape crop model | **Not implemented** |
| Slide Transition | **Not implemented** |

Current verdict: **capability map exists; most of the map is still empty**.
`native_depth_is_shallow()` remains true while unimplemented rows outnumber
fully implemented ones.

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

### Chart / table dual export

`ChartExportMode` selects how charts and tables are packaged:

| Mode | Behavior |
| --- | --- |
| `CROSS_APP_STABLE` (default) | Shape-baked bars / text grids / preview images — stable across apps |
| `NATIVE_DATA_BACKED` | PptxGenJS `addChart` / `addTable` with editable data (charts embed a workbook) |

Delivery UI exposes the choice under **导出策略 → 图表/表格导出**. Scene nodes
`ChartNode` / `TableNode` carry series and grid payloads; without data, export
falls back to image/text placeholders.

`FILL_NATIVE_TEMPLATE` remains Partial: structured *generation* is available, but
filling an existing enterprise template while preserving that file's original
OOXML master/layout identities in place is not yet complete.

Canonical SVG may be explored as a renderer backend, but it must not replace
`RenderScene` as authored state.

Design ideas were informed by the MIT-licensed `hugohe3/ppt-master` project; this
implementation uses Archium's own domain model and contains no copied converter
code. Inspiration does **not** imply feature parity with ppt-master native depth.
