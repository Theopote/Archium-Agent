/**
 * Native Slide Master / Layout / Placeholder definitions for STRUCTURED export.
 *
 * PptxGenJS maps each layout to one defineSlideMaster() call. That emits both
 * ppt/slideMasters/slideMasterN.xml and ppt/slideLayouts/slideLayoutN.xml with
 * Layout → Master and Slide → Layout relationships in the OOXML package.
 */

/**
 * @typedef {object} PlaceholderSpec
 * @property {string} id
 * @property {string} name
 * @property {string} placeholder_type
 * @property {string} [semantic_role]
 * @property {number} x
 * @property {number} y
 * @property {number} width
 * @property {number} height
 * @property {number} [idx]
 * @property {string} [prompt_text]
 */

/**
 * @typedef {object} SlideMasterSpec
 * @property {string} id
 * @property {string} name
 * @property {string[]} [fixed_scene_node_ids]
 * @property {string} [background_color]
 */

/**
 * @typedef {object} SlideLayoutSpec
 * @property {string} id
 * @property {string} master_id
 * @property {string} name
 * @property {PlaceholderSpec[]} [placeholder_specs]
 * @property {string[]} [layout_families]
 */

/**
 * @typedef {object} PresentationStructureSpec
 * @property {"flat"|"structured"} mode
 * @property {string} [default_layout_id]
 * @property {SlideMasterSpec[]} masters
 * @property {SlideLayoutSpec[]} layouts
 */

/**
 * @param {import('pptxgenjs').default} pres
 * @param {PresentationStructureSpec} structure
 * @param {{ width?: number, height?: number, background?: string }} [page]
 */
export function defineStructuredMasters(pres, structure, page = {}) {
  if (!structure || structure.mode !== "structured") {
    return;
  }
  const width = Number(page.width) || 10;
  const height = Number(page.height) || 5.625;
  const layoutName = "ARCHIUM_STRUCTURED_LAYOUT";
  pres.defineLayout({ name: layoutName, width, height });
  pres.layout = layoutName;

  const mastersById = new Map(
    (structure.masters || []).map((master) => [master.id, master]),
  );

  for (const layout of structure.layouts || []) {
    const master = mastersById.get(layout.master_id);
    const background = _stripHash(
      master?.background_color || page.background || "FFFFFF",
    );
    /** @type {object[]} */
    const objects = [];
    for (const placeholder of layout.placeholder_specs || []) {
      objects.push({
        placeholder: {
          options: {
            name: placeholder.name,
            type: placeholder.placeholder_type || "body",
            x: Number(placeholder.x) || 0,
            y: Number(placeholder.y) || 0,
            w: Number(placeholder.width) || 1,
            h: Number(placeholder.height) || 0.4,
          },
          text: placeholder.prompt_text || "",
        },
      });
    }
    // Deep-copy objects: pptxgenjs mutates placeholder config in place.
    pres.defineSlideMaster({
      title: layout.name,
      background: { color: background },
      objects: JSON.parse(JSON.stringify(objects)),
    });
  }
}

/**
 * @param {PresentationStructureSpec | null | undefined} structure
 * @param {string | null | undefined} layoutFamily
 * @returns {SlideLayoutSpec | null}
 */
export function resolveLayoutForFamily(structure, layoutFamily) {
  if (!structure || structure.mode !== "structured") {
    return null;
  }
  const family = String(layoutFamily || "").trim();
  if (family) {
    for (const layout of structure.layouts || []) {
      if ((layout.layout_families || []).includes(family)) {
        return layout;
      }
    }
  }
  const defaultId = structure.default_layout_id;
  if (defaultId) {
    return (structure.layouts || []).find((layout) => layout.id === defaultId) || null;
  }
  return (structure.layouts || [])[0] || null;
}

/**
 * Map a freeform element role / content_type onto a placeholder name.
 * @param {SlideLayoutSpec} layout
 * @param {object} element
 * @param {Set<string>} usedNames
 * @returns {string | null}
 */
export function matchPlaceholderName(layout, element, usedNames) {
  const specs = layout.placeholder_specs || [];
  if (!specs.length) {
    return null;
  }
  const role = String(element.role || "").toLowerCase();
  const contentType = String(element.content_type || "").toLowerCase();

  const preferredRoles = [];
  if (role === "title" || role === "section_title") {
    preferredRoles.push("title");
  } else if (role === "subtitle") {
    preferredRoles.push("subtitle", "body");
  } else if (role === "caption" || role === "source" || role === "footnote") {
    preferredRoles.push("caption", "body");
  } else if (
    contentType === "image" ||
    contentType === "drawing" ||
    role === "hero" ||
    role === "hero_image" ||
    role === "drawing"
  ) {
    preferredRoles.push(
      contentType === "drawing" || role === "drawing" ? "drawing" : "hero_image",
      "supporting_image",
      "drawing",
      "image_left",
      "image_right",
    );
  } else if (contentType === "chart") {
    preferredRoles.push("chart", "body");
  } else if (contentType === "table") {
    preferredRoles.push("table", "body");
  } else {
    preferredRoles.push("body", "subtitle", "caption");
  }

  for (const semantic of preferredRoles) {
    const hit = specs.find(
      (spec) =>
        !usedNames.has(spec.name) &&
        (spec.semantic_role === semantic || spec.name === semantic),
    );
    if (hit) {
      return hit.name;
    }
  }

  // Type-level fallback: first unused placeholder of compatible kind.
  const kind =
    contentType === "image" || contentType === "drawing"
      ? "image"
      : contentType === "chart"
        ? "chart"
        : contentType === "table"
          ? "table"
          : role === "title"
            ? "title"
            : "body";
  const typed = specs.find(
    (spec) => !usedNames.has(spec.name) && spec.placeholder_type === kind,
  );
  return typed ? typed.name : null;
}

/** @param {string | undefined} value */
function _stripHash(value) {
  if (!value) {
    return "FFFFFF";
  }
  return String(value).replace(/^#/, "").toUpperCase();
}
