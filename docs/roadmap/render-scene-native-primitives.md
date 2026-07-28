# RenderScene Native Primitives — Phased Implementation

> **Status:** Active plan (2026-07-28)  
> **Scope:** Five high-ROI PowerPoint-native constructs — **not** full ppt-master parity.  
> **Prerequisite:** Close **UI-006** / **ST-007** (Playbook E human loop) before expanding native depth.  
> **Honest boundary:** See [`powerpoint-capability-contract.md`](../architecture/powerpoint-capability-contract.md) and [`QUALITY_GATE_STATUS.md`](../QUALITY_GATE_STATUS.md).

---

## 0. Why this plan exists

RenderScene V1 closes the minimal loop (`Text` / `Image` / `Drawing` / `Shape`). Chart/Table are partial. Group, Connector, Gradient, Freeform, Pattern, Glow, and Transition are **not implemented**.

That gap limits visual polish (nested components, mixed-type text, analysis diagrams, soft fades, silhouettes) but **does not justify** a one-shot “implement all of PowerPoint” effort.

This document sequences five primitives by **visual ROI × structural leverage × implementation risk**.

---

## 1. Current baseline (do not re-litigate)

| Area | Today | Gap |
|------|-------|-----|
| `BaseRenderNode.group_id` | Field exists on every node | **A1 landed (PARTIAL):** `GroupNode` + Studio group/ungroup; export still flat siblings with `group_id` until `p:grpSp` |
| `TextNode` | Single-style `text` + optional `paragraphs` + **`runs` (A2)** | Per-run font/weight/color within one box when `runs` populated; empty `runs` keeps single-style fallback |
| Connectors | `ShapeNode` line only | **A3 landed (PARTIAL):** `ConnectorNode` + Studio connect; PPTX line/elbow arrows (approx until `p:cxnSp`) |
| Gradient | `image_mask=gradient_fade` approximated as solid rect overlay in `from-plan.mjs` | No `a:gradFill` on shape/image |
| Freeform | Circle mask via `OVAL` + image fill | No `a:custGeom` / polygon path |
| Export path | `RenderScene` → layout instructions → `render-plan.mjs` / PptxGenJS | New nodes must thread domain → adapter → JS renderer → closure manifest |

**Deferred (out of this plan):** Pattern fill, Glow, Shadow fidelity, Slide Transition, Preset Shape library, full Chart/Table styling depth.

---

## 2. Phased delivery

```text
Prerequisite: UI-006 / ST-007 pass (Playbook E)
        │
        ▼
Phase A (structural + typography)
  A1 GroupNode
  A2 Text Run Styling
  A3 ConnectorNode
        │
        ▼  (each item: domain → export → Studio smoke → Playbook E regression)
Phase B (visual depth)
  B1 GradientFill
  B2 Freeform / Polygon
```

| Phase | Items | Target outcome |
|-------|-------|----------------|
| **A** | Group, Text runs, Connector | Editable composite objects; mixed-style titles; real diagram links |
| **B** | Gradient, Freeform | Hero fades, masks, analysis silhouettes without raster bake |

**Rule:** Ship **one primitive per merge window**. Each merge must include domain model, export, closure assessment, unit tests, and one golden or integration export test.

---

## 3. Phase A — Structural primitives

### A1 — `GroupNode`

**Problem:** Multi-element cards (icon + label + badge) move independently; z-order edits are fragile.

**Domain (`archium/domain/visual/render_scene.py`):**

```python
class GroupNode(BaseRenderNode):
    node_type: Literal["group"] = "group"
    children: list[str]  # child node ids; max depth 4
    clip_children: bool = False
```

- Children keep absolute scene coordinates (V1 — no nested local frames).
- `group_id` on children must match parent `id` when grouped.
- Validator: no cycles, depth ≤ 4, all children on same slide.

**Export (`pptxgen/layouts/from-plan.mjs`):**

- Emit `p:grpSp` via PptxGenJS group API when available; else post-process OOXML `grpSp` wrapper.
- Group transform applies to children on export; Studio stores child absolute coords.

**Studio:**

- Multi-select → **组合** / **取消组合**
- Group drag moves all children; group resize scales children proportionally (V1: uniform scale only).
- Selection: click child selects child; click group bbox selects group.

**Tests:**

- `tests/unit/domain/test_group_node_validation.py`
- `tests/integration/render/test_group_pptx_export.py` — group moves as one unit in PPTX
- Studio geometry command test for group move

**Minimal acceptance (Playbook E extension):**

- [ ] Create group from 2+ nodes on worst slide
- [ ] Drag group; children move together
- [ ] Export PPTX; PowerPoint shows grouped objects (ungroup reveals children)
- [ ] Undo group create / ungroup

**Capability inventory:** `group` → `PARTIAL` (flat coords, uniform scale only).

---

### A2 — Text Run Styling

**Problem:** Titles need mixed CN/EN weights, accent color spans, and metric emphasis in one text box.

**Domain:**

```python
class TextRun(DomainModel):
    text: str
    font_family: str = ""
    font_family_cjk: str = ""
    font_family_latin: str = ""
    font_size: float | None = None
    font_weight: int | None = None
    font_style: str = "normal"
    color: str = ""
    color_token: str = ""

class TextNode(BaseRenderNode):
  # existing fields remain fallback when runs is empty
    runs: list[TextRun] = Field(default_factory=list)
```

- If `runs` non-empty, `text` is derived (`"".join(r.text for r in runs)`) for search/QA.
- `replace_text_node_content()` updates single run or collapses to one run.
- Theme tokens resolve per-run at compile time.

**Export:**

- `renderTextElement` passes PptxGenJS array form: `[{ text, options: { bold, color, fontFace, fontSize } }, ...]`.
- Preserve line breaks via `breakLine: true` on run boundaries.

**Studio:**

- Property panel: **basic** run editor (select substring → weight/color) in V1; no full rich-text toolbar.
- AI proposal path must round-trip runs or flatten with warning in manifest.

**Tests:**

- `tests/unit/domain/test_text_run_validation.py`
- `tests/unit/render/test_text_run_pptx_adapter.py` — mixed-weight title exports
- Golden: one slide with `中文 Title` + `EN subtitle` different weights

**Minimal acceptance:**

- [ ] Edit title with two styles in one box (e.g. bold Chinese + regular English)
- [ ] Export; PowerPoint shows mixed formatting in one shape
- [ ] Studio text save → export round-trip (addresses current E3 blocker class)

**Capability inventory:** `text` limitations updated — "single-style fallback; multi-run native when `runs` populated".

---

### A3 — `ConnectorNode`

**Problem:** Flow diagrams and analysis links use disconnected lines; no anchor semantics.

**Domain:**

```python
class ConnectorEndpoint(DomainModel):
    node_id: str
    anchor: Literal["center", "top", "bottom", "left", "right"] = "center"
    offset_x: float = 0
    offset_y: float = 0

class ConnectorNode(BaseRenderNode):
    node_type: Literal["connector"] = "connector"
    start: ConnectorEndpoint
    end: ConnectorEndpoint
    routing: Literal["straight", "elbow", "curve"] = "straight"
    stroke_color: str = "#333333"
    stroke_width: float = 1.5
    arrow_start: bool = False
    arrow_end: bool = True
    label: str = ""
```

- Bounding box (`x,y,width,height`) is derived from endpoints for hit-testing.
- Moving anchored node updates connector on next compile (reactive layout hook).

**Export:**

- PptxGenJS `addShape('line', …)` with arrow heads for V1 straight connectors.
- `p:cxnSp` with connection sites is **stretch goal**; document as `APPROXIMATE` until OOXML post-pass lands.

**Studio:**

- Tool: connect two nodes (pick start → pick end).
- Select connector → change routing / arrow / stroke.

**Tests:**

- Endpoint resolution unit tests
- Export test: connector between two shapes survives PPTX open
- Move anchored shape → connector endpoints update

**Minimal acceptance:**

- [ ] Draw connector between two elements on analysis slide
- [ ] Move one element; connector still attaches (after refresh or live update)
- [ ] Export; visible arrow link in PowerPoint

**Capability inventory:** `connector` → `PARTIAL` (straight/elbow; approximate `cxnSp`).

---

## 4. Phase B — Visual depth primitives

### B1 — `GradientFill`

**Problem:** Hero images and section backgrounds need soft fades; current `gradient_fade` mask is a flat translucent rect.

**Domain:**

```python
class GradientStop(DomainModel):
    position: float = Field(ge=0, le=1)
    color: str

class GradientFill(DomainModel):
    kind: Literal["linear", "radial"] = "linear"
    angle_deg: float = 0  # linear only
    stops: list[GradientStop]  # min 2

# On ShapeNode / ImageNode (V1):
    fill: GradientFill | None = None  # replaces solid fill_color when set
```

**Export:**

- PptxGenJS `fill: { type: 'gradient', … }` on shapes; image fade via gradient overlay shape (not raster bake).
- Replace ad-hoc `gradient_fade` rect hack in `from-plan.mjs` with shared gradient helper.

**Studio:**

- Property: fill type solid | linear gradient; 2-stop editor (V1).

**Tests:**

- Gradient serialization round-trip
- Export golden: hero slide with bottom fade
- Manifest notes `APPROXIMATE` when angle/stop count exceeds PptxGenJS support

**Minimal acceptance:**

- [ ] Apply bottom fade to hero image
- [ ] Export; fade visible in PowerPoint without raster flatten
- [ ] Edit stop color; re-export updates

**Capability inventory:** `gradient_fill` → `PARTIAL`.

---

### B2 — `Freeform` / `Polygon`

**Problem:** Silhouettes, site boundaries, and analysis zones need non-rectangular masks.

**Domain:**

```python
class FreeformNode(BaseRenderNode):
    node_type: Literal["freeform"] = "freeform"
    points: list[Point]  # normalized 0–1 within bbox OR absolute scene coords (pick absolute V1)
    closed: bool = True
    fill_color: str | None = None
    stroke_color: str | None = None
    stroke_width: float = 1.0
```

- V1: convex polygons + axis-aligned rects only; concave paths → `APPROXIMATE` or reject with manifest warning.
- `image_mask=silhouette` migrates to Freeform clip when available.

**Export:**

- PptxGenJS custom geometry if supported; else `custGeom` OOXML post-pass (spike required before commit).

**Studio:**

- V1 authoring: rectangle/circle mask presets + point-edit mode (advanced).
- No freehand pen in V1.

**Tests:**

- Polygon validation (min 3 points, closed)
- Export open/close in PowerPoint
- Silhouette mask regression vs current rect overlay

**Minimal acceptance:**

- [ ] Create triangular analysis zone overlay
- [ ] Use as image mask on one slide
- [ ] Export; shape editable in PowerPoint (not flattened image)

**Capability inventory:** `freeform_path` → `PARTIAL` (polygon only in V1).

---

## 5. Cross-cutting work (every item)

| Layer | Required change |
|-------|-----------------|
| `powerpoint_capability.py` | Add `RENDER_SCENE_V1_CAPABILITIES` entries; update `POWERPOINT_NATIVE_DEPTH_INVENTORY` status |
| `PowerPointContractService` | Emission planning for new node types; closure rules for group children |
| `layout_plan_adapter.py` / scene→instructions | Serialize new fields |
| `from-plan.mjs` | Render handlers |
| `DeckExportManifest` | Record fidelity downgrades |
| Studio commands | Group, connector, gradient, freeform editors |
| Docs | Update `QUALITY_GATE_STATUS.md` claim row when each primitive ships |

**Forbidden until substantially green:** "深度原生 PowerPoint", "PowerPoint-complete", "与 PowerPoint 对象模型等价".

---

## 6. Regression gate (after each primitive)

1. `python scripts/run_playbook_e_gate.py -q` — green
2. New primitive unit + export integration tests — green
3. One human or scripted Playbook E spot-check on the new capability
4. `native_depth_is_shallow()` still returns `True` until Phase B complete + inventory review

---

## 7. Suggested calendar (indicative)

| Week | Deliverable |
|------|-------------|
| 0 | UI-006 / ST-007 human pass |
| 1–2 | A1 GroupNode |
| 2–3 | A2 Text Run Styling (+ fix Studio→PPTX text round-trip) |
| 4 | A3 ConnectorNode |
| 5 | B1 GradientFill |
| 6–7 | B2 Freeform spike → polygon V1 |

Adjust after A2 if Playbook E exposes additional export sync bugs.

---

## 8. References

- Capability contract: [`docs/architecture/powerpoint-capability-contract.md`](../architecture/powerpoint-capability-contract.md)
- Domain model: `archium/domain/visual/render_scene.py`
- Depth inventory: `archium/domain/powerpoint_capability.py`
- PPTX renderer: `archium/infrastructure/renderers/pptxgen/layouts/from-plan.mjs`
- Human acceptance: [`docs/rehearsal/playbook-e-checklist.md`](../rehearsal/playbook-e-checklist.md)
