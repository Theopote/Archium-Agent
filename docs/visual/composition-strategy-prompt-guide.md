# Composition Strategy — LLM Prompt Guide

## Overview

When generating `VisualIntent` for a slide, the LLM should now output a **structured `CompositionStrategy`** instead of a freeform string. This captures the architectural design judgment that precedes layout geometry.

## Required Fields

Every `CompositionStrategy` must specify:

```json
{
  "archetype": "architectural_editorial",
  "dominant_axis": "horizontal",
  "reading_path": "z_pattern",
  "tension": "asymmetric",
  "balance": "left_weighted",
  "image_role": "dominant",
  "typography_role": "editorial",
  "white_space": "generous"
}
```

## Field Definitions

### `archetype` (string)
The high-level design pattern name. Common values:
- `"architectural_editorial"` — Magazine-style layout, hero image + editorial text
- `"technical_diagram"` — Precision-focused, annotated technical drawing
- `"hero_statement"` — Single large visual with minimal text
- `"data_narrative"` — Chart or table with supporting text
- `"section_reveal"` — Diagonal section cut with layered annotations

### `dominant_axis` (enum)
Primary structural axis organizing the composition:
- `"horizontal"` — Left-right flow, landscape emphasis
- `"vertical"` — Top-down hierarchy, vertical section
- `"diagonal"` — Dynamic movement, architectural section cut
- `"radial"` — Central focus with radiating elements
- `"none"` — No dominant axis, grid or scattered

### `reading_path` (enum)
Expected audience eye movement:
- `"linear_ltr"` — Left-to-right, simple narrative
- `"z_pattern"` — Title → hero → text, classic editorial
- `"f_pattern"` — Scan-heavy, data or list
- `"focal_radial"` — Central hero outward
- `"layered"` — Background → midground → foreground depth

### `tension` (enum)
Structural balance strategy:
- `"symmetric"` — Mirrored balance, formal
- `"asymmetric"` — Unequal but balanced, editorial
- `"dynamic"` — Intentional imbalance, movement
- `"static"` — Stable, grounded, architectural plan view

### `balance` (enum)
Weight distribution across the page:
- `"centered"` — Central mass, symmetry
- `"left_weighted"` — Western reading, editorial
- `"right_weighted"` — Reveal, unexpected
- `"top_heavy"` — Hero image or title dominance
- `"bottom_anchored"` — Grounded, landscape baseline

### `image_role` (enum)
The design function of imagery:
- `"dominant"` — Hero, primary visual narrative
- `"supporting"` — Evidence, context
- `"ambient"` — Background texture, mood
- `"evidence"` — Technical proof, diagram
- `"absent"` — Text or data only

### `typography_role` (enum)
The design function of type:
- `"hero"` — Large title as primary visual element
- `"editorial"` — Balanced text and image
- `"data_label"` — Annotations, technical callouts
- `"narrative"` — Body copy, explanation
- `"minimal"` — Sparse labels only

### `white_space` (enum)
How negative space is deployed:
- `"generous"` — Architecture cover, monumental
- `"balanced"` — Standard analysis page
- `"compact"` — Data-dense, technical
- `"strategic"` — Localized negative space for emphasis

## Optional Fields

### `focal_point` (tuple or null)
Visual center of gravity as `[x%, y%]` from top-left. Use `null` for no single focus.

```json
"focal_point": [0.35, 0.45]
```

### `visual_hierarchy` (array of strings)
Ordered importance of elements:

```json
"visual_hierarchy": ["hero_image", "title", "body_text", "annotation"]
```

### `rhythm` (string)
Element repetition pattern:
- `"repetitive"` — Consistent grid
- `"varied"` — Mixed sizes/positions
- `"progressive"` — Gradual transformation

### `diagram_role` (string or null)
Diagram treatment if present:
- `"annotated"` — Labels and callouts
- `"standalone"` — Clean, no text overlay
- `"layered"` — Multiple depth planes

### `margins` (enum)
Edge treatment:
- `"generous"` — Wide margins, luxury
- `"standard"` — Balanced professional
- `"tight"` — Maximum content density
- `"asymmetric"` — One side open, editorial

### `layering` (enum)
Depth strategy:
- `"flat"` — Single plane, diagram clarity
- `"subtle_depth"` — Slight overlap, shadows
- `"pronounced"` — Strong foreground/background separation

### `drawing_priority` (float, 0-1)
Importance of technical drawings vs. photos:
- `0.0` — Photos only
- `0.5` — Balanced
- `1.0` — Drawings only

### `precision_level` (string)
Technical precision:
- `"loose"` — Conceptual, artistic
- `"balanced"` — Mixed
- `"precise"` — Engineering accuracy

### `annotation_density` (string)
Callout/label density:
- `"sparse"` — Minimal labels
- `"moderate"` — Balanced
- `"dense"` — Heavy annotation

## Example Prompts

### Example 1: Hero Image Slide

**Input**: SlideSpec with large site photo, short title, minimal text

**Output**:
```json
{
  "composition_strategy": {
    "archetype": "hero_statement",
    "dominant_axis": "none",
    "focal_point": [0.5, 0.5],
    "visual_hierarchy": ["hero_image", "title"],
    "reading_path": "focal_radial",
    "tension": "static",
    "balance": "centered",
    "rhythm": "progressive",
    "image_role": "dominant",
    "typography_role": "hero",
    "white_space": "generous",
    "margins": "generous",
    "layering": "subtle_depth",
    "drawing_priority": 0.2,
    "precision_level": "loose",
    "annotation_density": "sparse"
  }
}
```

### Example 2: Technical Section Drawing

**Input**: SlideSpec with annotated architectural section, callouts, dimensions

**Output**:
```json
{
  "composition_strategy": {
    "archetype": "section_reveal",
    "dominant_axis": "diagonal",
    "focal_point": [0.4, 0.6],
    "visual_hierarchy": ["section_drawing", "title", "key_labels"],
    "reading_path": "layered",
    "tension": "dynamic",
    "balance": "left_weighted",
    "rhythm": "progressive",
    "image_role": "dominant",
    "typography_role": "data_label",
    "diagram_role": "layered",
    "white_space": "strategic",
    "margins": "asymmetric",
    "layering": "pronounced",
    "drawing_priority": 0.95,
    "precision_level": "precise",
    "annotation_density": "moderate"
  }
}
```

### Example 3: Data Comparison

**Input**: SlideSpec with comparison table or chart, title, insight text

**Output**:
```json
{
  "composition_strategy": {
    "archetype": "data_narrative",
    "dominant_axis": "horizontal",
    "focal_point": null,
    "visual_hierarchy": ["chart", "title", "insight_text"],
    "reading_path": "linear_ltr",
    "tension": "symmetric",
    "balance": "centered",
    "rhythm": "repetitive",
    "image_role": "supporting",
    "typography_role": "data_label",
    "white_space": "compact",
    "margins": "tight",
    "layering": "flat",
    "drawing_priority": 0.4,
    "precision_level": "precise",
    "annotation_density": "moderate"
  }
}
```

### Example 4: Editorial Analysis

**Input**: SlideSpec with analysis text, supporting photo, annotations

**Output**:
```json
{
  "composition_strategy": {
    "archetype": "architectural_editorial",
    "dominant_axis": "horizontal",
    "focal_point": [0.35, 0.45],
    "visual_hierarchy": ["hero_image", "title", "body_text"],
    "reading_path": "z_pattern",
    "tension": "asymmetric",
    "balance": "left_weighted",
    "rhythm": "varied",
    "image_role": "dominant",
    "typography_role": "editorial",
    "white_space": "generous",
    "margins": "generous",
    "layering": "subtle_depth",
    "drawing_priority": 0.3,
    "precision_level": "balanced",
    "annotation_density": "sparse"
  }
}
```

## Decision Tree

Use this to choose the right archetype:

```
Has technical drawing?
├─ Yes + low text → "section_reveal" or "technical_diagram"
├─ Yes + moderate text → "technical_diagram"
└─ No
   ├─ Has data chart? → "data_narrative"
   └─ Has large image?
      ├─ Yes + low text → "hero_statement"
      └─ Yes + moderate text → "architectural_editorial"
```

## Integration with Layout Generation

The `LayoutPlanningService` will read these structured fields to:

1. **Select appropriate LayoutFamily** based on `archetype` and `image_role`
2. **Configure geometry** using `balance`, `tension`, `margins`
3. **Determine reading order** from `reading_path` and `visual_hierarchy`
4. **Adjust whitespace** based on `white_space` strategy
5. **Priority-weight elements** using `drawing_priority` and role fields

## Backward Compatibility

Existing systems with `composition_strategy: str` will continue to work. The field accepts:
- `CompositionStrategy` object (new)
- `string` (legacy)
- `dict` (auto-converted to object)
- `null`

Use `VisualIntent.has_structured_composition()` to check if structured strategy is present.
