/**
 * Execute-only LayoutPlan renderer.
 * Places each element at instruction x/y/w/h — does not choose family or recompute layout.
 *
 * STRUCTURED mode additionally binds slides to declared masters/layouts and fills
 * placeholders by semantic role when possible; unmatched elements remain freeform.
 */

import {
  defineStructuredMasters,
  matchPlaceholderName,
  resolveLayoutForFamily,
} from "../core/structure.mjs";

/**
 * @param {import('pptxgenjs').default} pres
 * @param {object} tokens theme_tokens from RenderedSlideInstruction
 * @param {object | null} [structure] PresentationStructureSpec payload
 */
export function applyPlanLayout(pres, tokens, structure = null) {
  const page = tokens?.page ?? {};
  const width = Number(page.width) || 10;
  const height = Number(page.height) || 5.625;
  const colors = tokens?.colors ?? {};
  const background = _stripHash(colors.background || colors.white || "FFFFFF");

  if (structure && structure.mode === "structured") {
    defineStructuredMasters(pres, structure, { width, height, background });
    return;
  }

  const layoutName = "ARCHIUM_PLAN_LAYOUT";
  pres.defineLayout({ name: layoutName, width, height });
  pres.layout = layoutName;

  pres.defineSlideMaster({
    title: "ARCHIUM_PLAN_MASTER",
    background: { color: background },
    // Page numbers come from LayoutPlan elements when present — do not auto-inject.
  });
}

/**
 * @param {import('pptxgenjs').default} pres
 * @param {object} slideInstruction RenderedSlideInstruction-shaped object
 * @param {object} [deckTheme] optional deck-level theme fallback
 * @param {object | null} [structure] PresentationStructureSpec payload
 */
export function renderSlideFromPlan(pres, slideInstruction, deckTheme = null, structure = null) {
  const layout = resolveLayoutForFamily(structure, slideInstruction.layout_family);
  const masterName = layout?.name || "ARCHIUM_PLAN_MASTER";
  const page = pres.addSlide({ masterName });
  const usedPlaceholders = new Set();
  const elements = Array.isArray(slideInstruction.elements)
    ? [...slideInstruction.elements].sort(
        (a, b) => Number(a.z_index ?? 0) - Number(b.z_index ?? 0),
      )
    : [];

  for (const element of elements) {
    const placeholderName =
      layout != null ? matchPlaceholderName(layout, element, usedPlaceholders) : null;
    if (placeholderName) {
      usedPlaceholders.add(placeholderName);
    }
    renderElement(pres, page, element, slideInstruction, deckTheme, placeholderName);
  }

  if (slideInstruction.speaker_notes) {
    page.addNotes(String(slideInstruction.speaker_notes));
  }
}

/**
 * @param {import('pptxgenjs').default} pres
 * @param {object} page
 * @param {object} element
 * @param {object} slideInstruction
 * @param {object | null} deckTheme
 * @param {string | null} placeholderName
 */
function renderElement(pres, page, element, slideInstruction, deckTheme, placeholderName) {
  const contentType = element.content_type ?? "text";
  if (contentType === "image" || contentType === "drawing") {
    renderImageElement(pres, page, element, slideInstruction, deckTheme, placeholderName);
    return;
  }
  if (contentType === "shape") {
    // Shapes stay freeform — native placeholders are text/image/chart/table.
    renderShapeElement(pres, page, element, slideInstruction);
    return;
  }
  if (contentType === "chart" || contentType === "table") {
    renderPlaceholderBox(pres, page, element, slideInstruction, contentType, placeholderName);
    return;
  }
  // text | metric | default
  renderTextElement(page, element, placeholderName);
}

/** @param {object} page @param {object} element @param {string | null} placeholderName */
function renderTextElement(page, element, placeholderName = null) {
  const text = element.text;
  if (text == null || String(text).trim() === "") {
    return;
  }
  const fontSize = Number(element.font_size) || 16;
  const bold =
    element.font_weight === "bold" ||
    Number(element.font_weight) >= 600 ||
    element.role === "title" ||
    element.role === "metric";
  /** @type {Record<string, unknown>} */
  const opts = {
    fontSize,
    bold,
    color: _stripHash(element.color || "1A1A1A"),
    fontFace: element.font_family_cjk || element.font_family || "Microsoft YaHei",
    align: _align(element.alignment),
    valign: element.role === "metric" ? "mid" : "top",
  };
  if (placeholderName) {
    opts.placeholder = placeholderName;
  } else {
    opts.x = Number(element.x) || 0;
    opts.y = Number(element.y) || 0;
    opts.w = Number(element.w) || 1;
    opts.h = Number(element.h) || 0.3;
  }
  page.addText(String(text), opts);
}

/**
 * @param {import('pptxgenjs').default} pres
 * @param {object} page
 * @param {object} element
 * @param {object} slideInstruction
 * @param {object | null} deckTheme
 * @param {string | null} placeholderName
 */
function renderImageElement(pres, page, element, slideInstruction, deckTheme, placeholderName) {
  const rect = {
    x: Number(element.x) || 0,
    y: Number(element.y) || 0,
    w: Number(element.w) || 1,
    h: Number(element.h) || 1,
  };
  const path = element.path;
  if (path) {
    const fitMode = element.fit_mode || (element.content_type === "drawing" ? "contain" : "cover");
    /** @type {Record<string, unknown>} */
    const opts = { path };
    if (placeholderName) {
      opts.placeholder = placeholderName;
    } else {
      opts.x = rect.x;
      opts.y = rect.y;
      opts.w = rect.w;
      opts.h = rect.h;
      if (fitMode === "contain" || fitMode === "cover") {
        opts.sizing = { type: fitMode, w: rect.w, h: rect.h };
      }
    }
    page.addImage(opts);
    return;
  }

  const colors = slideInstruction.theme_tokens?.colors ?? deckTheme?.colors ?? {};
  const fill = _stripHash(colors.surface || colors.light || "F4F6F8");
  const line = _stripHash(colors.warning || colors.accent || colors.primary || "B45309");
  const muted = _stripHash(colors.muted_text || colors.muted || "666666");
  if (!placeholderName) {
    page.addShape(pres.shapes.RECTANGLE, {
      x: rect.x,
      y: rect.y,
      w: rect.w,
      h: rect.h,
      fill: { color: fill },
      line: {
        color: line,
        width: element.asset_unresolved ? 1.5 : 1,
        dashType: element.asset_unresolved ? "dash" : undefined,
      },
    });
  }
  let label = element.content_type === "drawing" ? "图纸占位" : "图片占位";
  if (element.asset_unresolved) {
    const code = element.asset_error || "LAYOUT.UNRESOLVED_ASSET_PATH";
    if (code === "LAYOUT.HERO_ASSET_MISSING") {
      label = "主图素材缺失";
    } else if (code === "LAYOUT.TECHNICAL_DRAWING_MISSING") {
      label = "技术图纸缺失";
    } else if (code === "LAYOUT.UNSUPPORTED_IMAGE_FORMAT") {
      label = "素材格式不支持";
    } else {
      label = "素材缺失/路径未解析";
    }
  }
  /** @type {Record<string, unknown>} */
  const textOpts = {
    fontSize: 12,
    color: muted,
    fontFace: element.font_family_cjk || element.font_family || "Microsoft YaHei",
    align: "center",
    valign: "mid",
  };
  if (placeholderName) {
    textOpts.placeholder = placeholderName;
  } else {
    textOpts.x = rect.x + 0.15;
    textOpts.y = rect.y + rect.h / 2 - 0.2;
    textOpts.w = Math.max(0.4, rect.w - 0.3);
    textOpts.h = 0.4;
  }
  page.addText(label, textOpts);
}

/**
 * @param {import('pptxgenjs').default} pres
 * @param {object} page
 * @param {object} element
 * @param {object} slideInstruction
 */
function renderShapeElement(pres, page, element, slideInstruction) {
  const colors = slideInstruction.theme_tokens?.colors ?? {};
  const fill = _stripHash(
    element.fill_color || colors.surface || colors.light || "F4F6F8",
  );
  const lineColor = _stripHash(
    element.stroke_color || colors.border || colors.muted_text || "D9D5CF",
  );
  const lineWidth = Number(element.stroke_width) || 0;
  page.addShape(pres.shapes.RECTANGLE, {
    x: Number(element.x) || 0,
    y: Number(element.y) || 0,
    w: Number(element.w) || 1,
    h: Number(element.h) || 0.3,
    fill: { color: fill },
    line: { color: lineColor, width: lineWidth },
  });
}

/**
 * @param {import('pptxgenjs').default} pres
 * @param {object} page
 * @param {object} element
 * @param {object} slideInstruction
 * @param {string} kind
 * @param {string | null} placeholderName
 */
function renderPlaceholderBox(pres, page, element, slideInstruction, kind, placeholderName) {
  if (!placeholderName) {
    renderShapeElement(pres, page, element, slideInstruction);
  }
  const colors = slideInstruction.theme_tokens?.colors ?? {};
  const muted = _stripHash(colors.muted_text || colors.muted || "666666");
  /** @type {Record<string, unknown>} */
  const opts = {
    fontSize: 12,
    color: muted,
    align: "center",
  };
  if (placeholderName) {
    opts.placeholder = placeholderName;
  } else {
    opts.x = Number(element.x) || 0;
    opts.y = (Number(element.y) || 0) + (Number(element.h) || 1) / 2 - 0.15;
    opts.w = Number(element.w) || 1;
    opts.h = 0.3;
  }
  page.addText(kind === "chart" ? "图表占位" : "表格占位", opts);
}

/** @param {string | undefined} value */
function _align(value) {
  if (value === "center" || value === "right") {
    return value;
  }
  return "left";
}

/** @param {string | undefined} value */
function _stripHash(value) {
  if (!value) {
    return "FFFFFF";
  }
  return String(value).replace(/^#/, "");
}
