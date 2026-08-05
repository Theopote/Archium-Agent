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
import { addCitationBlock } from "../components/citation.mjs";

/**
 * Approximate a linear gradient with stacked translucent rectangles (pptxgen 3.12).
 * @param {import('pptxgenjs').default} pres
 * @param {object} page
 * @param {{x:number,y:number,w:number,h:number}} rect
 * @param {object} fill
 * @param {number} [bandCount]
 */
function _applyGradientApprox(pres, page, rect, fill, bandCount = 8) {
  if (!pres.shapes?.RECTANGLE || !fill || !Array.isArray(fill.stops) || fill.stops.length < 2) {
    return;
  }
  const stops = [...fill.stops]
    .map((stop) => ({
      position: Math.max(0, Math.min(1, Number(stop.position) || 0)),
      color: _stripHash(stop.color || "1A1A1A"),
      transparency: Math.max(0, Math.min(1, Number(stop.transparency) || 0)),
    }))
    .sort((a, b) => a.position - b.position);
  const angle = ((Number(fill.angle_deg) || 0) % 360 + 360) % 360;
  const vertical = angle >= 45 && angle < 135;
  const reverse = angle >= 135 && angle < 315;
  const bands = Math.max(3, Math.min(bandCount, 16));

  /** @param {number} t */
  function sample(t) {
    if (t <= stops[0].position) {
      return stops[0];
    }
    if (t >= stops[stops.length - 1].position) {
      return stops[stops.length - 1];
    }
    for (let i = 0; i < stops.length - 1; i += 1) {
      const a = stops[i];
      const b = stops[i + 1];
      if (t >= a.position && t <= b.position) {
        const span = Math.max(b.position - a.position, 1e-6);
        const u = (t - a.position) / span;
        return {
          position: t,
          color: u < 0.5 ? a.color : b.color,
          transparency: a.transparency * (1 - u) + b.transparency * u,
        };
      }
    }
    return stops[stops.length - 1];
  }

  for (let i = 0; i < bands; i += 1) {
    const t0 = i / bands;
    const t1 = (i + 1) / bands;
    const mid = (t0 + t1) / 2;
    const sampleT = reverse ? 1 - mid : mid;
    const stop = sample(sampleT);
    const transparency = Math.round(stop.transparency * 100);
    if (transparency >= 99) {
      continue;
    }
    /** @type {Record<string, unknown>} */
    const opts = {
      fill: { color: stop.color },
      line: { color: stop.color, width: 0 },
      transparency,
    };
    if (vertical) {
      opts.x = rect.x;
      opts.y = rect.y + rect.h * t0;
      opts.w = rect.w;
      opts.h = Math.max(rect.h / bands, 0.01);
    } else {
      opts.x = rect.x + rect.w * t0;
      opts.y = rect.y;
      opts.w = Math.max(rect.w / bands, 0.01);
      opts.h = rect.h;
    }
    page.addShape(pres.shapes.RECTANGLE, opts);
  }
}

/**
 * Apply fill to a shape. PptxGenJS 3.12 has no reliable a:gradFill — use band approx.
 * @param {import('pptxgenjs').default} pres
 * @param {object} page
 * @param {object} shapeOpts base shape options (mutated fill)
 * @param {object | null | undefined} fill
 * @param {string | null | undefined} solidFallback
 * @returns {"native"|"solid"|"approx"|"none"}
 */
function _assignShapeFill(pres, page, shapeOpts, fill, solidFallback) {
  if (fill && Array.isArray(fill.stops) && fill.stops.length >= 2) {
    // Transparent base; bands drawn after the shape.
    shapeOpts.fill = { type: "none" };
    return "approx";
  }
  if (solidFallback) {
    shapeOpts.fill = { color: _stripHash(solidFallback) };
    return "solid";
  }
  return "none";
}
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
  // Prefer DesignSystem board tint; never fall back to pure white (reads as
  // "no color system" even when theme tokens were meant to be cool grey).
  const background = _stripHash(
    colors.background || colors.surface || "D9E2EA",
  );

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
export function renderSlideFromPlan(pres, slideInstruction, deckTheme = null, structure = null, chartExportMode = "cross_app_stable") {
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
    renderElement(
      pres,
      page,
      element,
      slideInstruction,
      deckTheme,
      placeholderName,
      chartExportMode,
    );
  }

  if (slideInstruction.speaker_notes) {
    page.addNotes(String(slideInstruction.speaker_notes));
  }

  const citationLines = Array.isArray(slideInstruction.citations)
    ? slideInstruction.citations.map((item) => String(item || "").trim()).filter(Boolean)
    : [];
  if (citationLines.length) {
    const pageW = Number(slideInstruction.page_width) || 10;
    const pageH = Number(slideInstruction.page_height) || 5.625;
    addCitationBlock(
      page,
      citationLines.slice(0, 4),
      {
        colors: { muted: "666666" },
        fonts: { caption: "Microsoft YaHei" },
        component_styles: { caption: { fontSize: 9 } },
      },
      { x: 0.4, y: pageH - 0.75, w: pageW - 0.8, h: 0.6 },
    );
  }
}

/**
 * @param {import('pptxgenjs').default} pres
 * @param {object} page
 * @param {object} element
 * @param {object} slideInstruction
 * @param {object | null} deckTheme
 * @param {string | null} placeholderName
 * @param {string} chartExportMode
 */
function renderElement(pres, page, element, slideInstruction, deckTheme, placeholderName, chartExportMode) {
  const contentType = element.content_type ?? "text";
  if (contentType === "group") {
    // V1: GroupNode is scene/Studio authoritative; children still render as flat
    // siblings carrying group_id until native p:grpSp post-pass lands.
    return;
  }
  if (contentType === "connector") {
    renderConnectorElement(pres, page, element);
    return;
  }
  if (contentType === "freeform") {
    renderFreeformElement(pres, page, element);
    return;
  }
  if (contentType === "image" || contentType === "drawing") {
    renderImageElement(pres, page, element, slideInstruction, deckTheme, placeholderName);
    return;
  }
  if (contentType === "shape") {
    // Shapes stay freeform — native placeholders are text/image/chart/table.
    renderShapeElement(pres, page, element, slideInstruction);
    return;
  }
  if (contentType === "chart") {
    renderChartElement(pres, page, element, slideInstruction, deckTheme, placeholderName, chartExportMode);
    return;
  }
  if (contentType === "table") {
    renderTableElement(pres, page, element, slideInstruction, deckTheme, placeholderName, chartExportMode);
    return;
  }
  // text | metric | default
  renderTextElement(page, element, placeholderName);
}

/**
 * @param {import('pptxgenjs').default} pres
 * @param {object} page
 * @param {object} element
 * @param {object} slideInstruction
 * @param {object | null} deckTheme
 * @param {string | null} placeholderName
 * @param {string} chartExportMode
 */
function renderChartElement(
  pres,
  page,
  element,
  slideInstruction,
  deckTheme,
  placeholderName,
  chartExportMode,
) {
  const series = Array.isArray(element.series) ? element.series : [];
  const hasData = series.some(
    (item) => Array.isArray(item?.values) && item.values.length > 0,
  );
  const native = chartExportMode === "native_data_backed" && hasData && !placeholderName;

  if (native) {
    const colors = slideInstruction.theme_tokens?.colors ?? deckTheme?.colors ?? {};
    page.addChart(
      element.chart_type || "bar",
      series.map((item) => ({
        name: item.name || "Series",
        labels: item.labels || [],
        values: item.values || [],
      })),
      {
        x: Number(element.x) || 0,
        y: Number(element.y) || 0,
        w: Number(element.w) || 1,
        h: Number(element.h) || 1,
        showLegend: element.show_legend !== false,
        showValue: Boolean(element.show_value),
        showTitle: Boolean(element.title),
        title: element.title || "",
        chartColors: [
          _stripHash(colors.primary || "1F3A5F"),
          _stripHash(colors.accent || "2E6DA4"),
          _stripHash(colors.secondary || colors.muted || "666666"),
        ],
      },
    );
    return;
  }

  // CROSS_APP_STABLE: prefer preview image, else bake simple bar shapes from data.
  if (element.path && !placeholderName) {
    renderImageElement(pres, page, element, slideInstruction, deckTheme, null);
    return;
  }
  if (hasData && !placeholderName) {
    renderChartAsShapes(pres, page, element, slideInstruction);
    return;
  }
  renderPlaceholderBox(pres, page, element, slideInstruction, "chart", placeholderName);
}

/**
 * @param {import('pptxgenjs').default} pres
 * @param {object} page
 * @param {object} element
 * @param {object} slideInstruction
 */
function renderChartAsShapes(pres, page, element, slideInstruction) {
  const series = Array.isArray(element.series) ? element.series : [];
  const primary = series[0] || { values: [], labels: [] };
  const values = (primary.values || []).map((v) => Number(v) || 0);
  const labels = primary.labels || [];
  const colors = slideInstruction.theme_tokens?.colors ?? {};
  const fill = _stripHash(colors.primary || colors.accent || "1F3A5F");
  const muted = _stripHash(colors.muted_text || colors.muted || "666666");
  const x0 = Number(element.x) || 0;
  const y0 = Number(element.y) || 0;
  const w = Number(element.w) || 1;
  const h = Number(element.h) || 1;
  const maxVal = Math.max(...values, 1);
  const gap = 0.08;
  const barW = values.length ? (w - gap * (values.length + 1)) / values.length : w;
  const chartBottom = y0 + h - 0.35;
  const chartTop = y0 + 0.15;
  const chartH = Math.max(0.4, chartBottom - chartTop);

  page.addShape(pres.shapes.RECTANGLE, {
    x: x0,
    y: y0,
    w,
    h,
    fill: { color: _stripHash(colors.surface || colors.light || "F4F6F8") },
    line: { color: _stripHash(colors.border || "D9D5CF"), width: 0.5 },
  });

  values.forEach((value, index) => {
    const barH = (Math.abs(value) / maxVal) * chartH;
    const bx = x0 + gap + index * (barW + gap);
    const by = chartBottom - barH;
    page.addShape(pres.shapes.RECTANGLE, {
      x: bx,
      y: by,
      w: Math.max(0.05, barW),
      h: Math.max(0.05, barH),
      fill: { color: fill },
      line: { color: fill, width: 0 },
    });
    const label = labels[index] != null ? String(labels[index]) : String(value);
    page.addText(label, {
      x: bx,
      y: chartBottom + 0.02,
      w: Math.max(0.05, barW),
      h: 0.28,
      fontSize: 9,
      color: muted,
      align: "center",
      valign: "top",
    });
  });
}

/**
 * @param {import('pptxgenjs').default} pres
 * @param {object} page
 * @param {object} element
 * @param {object} slideInstruction
 * @param {object | null} deckTheme
 * @param {string | null} placeholderName
 * @param {string} chartExportMode
 */
function renderTableElement(
  pres,
  page,
  element,
  slideInstruction,
  deckTheme,
  placeholderName,
  chartExportMode,
) {
  const headers = Array.isArray(element.headers) ? element.headers : [];
  const rows = Array.isArray(element.rows) ? element.rows : [];
  const hasData = headers.length > 0 && rows.length > 0;
  const native = chartExportMode === "native_data_backed" && hasData && !placeholderName;

  if (native) {
    const colors = slideInstruction.theme_tokens?.colors ?? deckTheme?.colors ?? {};
    const tableWidth = Number(element.w) || 1;
    const headerRow = headers.map((header) => ({
      text: String(header ?? ""),
      options: {
        bold: true,
        fill: { color: _stripHash(colors.surface || colors.light || "F4F6F8") },
        color: _stripHash(colors.primary || colors.primary_text || "1A1A1A"),
        fontSize: 12,
      },
    }));
    const bodyRows = rows.map((row) =>
      (Array.isArray(row) ? row : [row]).map((cell) => ({
        text: String(cell ?? ""),
        options: {
          color: _stripHash(colors.primary_text || colors.text || "1A1A1A"),
          fontSize: 11,
        },
      })),
    );
    page.addTable([headerRow, ...bodyRows], {
      x: Number(element.x) || 0,
      y: Number(element.y) || 0,
      w: tableWidth,
      colW: Array(headers.length).fill(tableWidth / Math.max(headers.length, 1)),
      border: {
        type: "solid",
        pt: 0.5,
        color: _stripHash(colors.border || colors.muted || "999999"),
      },
      margin: 0.04,
    });
    return;
  }

  if (hasData && !placeholderName) {
    renderTableAsTextGrid(page, element, slideInstruction);
    return;
  }
  renderPlaceholderBox(pres, page, element, slideInstruction, "table", placeholderName);
}

/**
 * @param {object} page
 * @param {object} element
 * @param {object} slideInstruction
 */
function renderTableAsTextGrid(page, element, slideInstruction) {
  const headers = element.headers || [];
  const rows = element.rows || [];
  const colors = slideInstruction.theme_tokens?.colors ?? {};
  const lines = [
    headers.map((h) => String(h ?? "")).join(" | "),
    ...rows.map((row) =>
      (Array.isArray(row) ? row : [row]).map((cell) => String(cell ?? "")).join(" | "),
    ),
  ];
  page.addText(lines.join("\n"), {
    x: Number(element.x) || 0,
    y: Number(element.y) || 0,
    w: Number(element.w) || 1,
    h: Number(element.h) || 1,
    fontSize: 11,
    color: _stripHash(colors.primary_text || colors.text || "1A1A1A"),
    fontFace: element.font_family_cjk || element.font_family || "Microsoft YaHei",
    valign: "top",
  });
}

/** @param {object} page @param {object} element @param {string | null} placeholderName */
function renderTextElement(page, element, placeholderName = null) {
  const text = element.text;
  const runs = Array.isArray(element.runs) ? element.runs : [];
  if ((!text || String(text).trim() === "") && runs.length === 0) {
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
  if (element.letter_spacing != null && Number(element.letter_spacing) !== 0) {
    // pptxgenjs: charSpacing is percentage of font size (approx em*100).
    opts.charSpacing = Math.round(Number(element.letter_spacing) * 100);
  }
  if (element.opacity != null && Number(element.opacity) < 1) {
    opts.transparency = Math.round((1 - Number(element.opacity)) * 100);
  }
  if (placeholderName) {
    opts.placeholder = placeholderName;
  } else {
    opts.x = Number(element.x) || 0;
    opts.y = Number(element.y) || 0;
    opts.w = Number(element.w) || 1;
    opts.h = Number(element.h) || 0.3;
  }
  if (runs.length > 0) {
    const payload = runs.map((run, index) => {
      const runText = String(run?.text ?? "");
      const weight = Number(run?.font_weight);
      const runBold =
        run?.font_weight === "bold" ||
        (!Number.isNaN(weight) && weight >= 600) ||
        (run?.font_weight == null && bold);
      /** @type {Record<string, unknown>} */
      const runOpts = {
        bold: runBold,
        color: _stripHash(run?.color || element.color || "1A1A1A"),
        fontFace:
          run?.font_family_cjk ||
          run?.font_family ||
          element.font_family_cjk ||
          element.font_family ||
          "Microsoft YaHei",
        fontSize: Number(run?.font_size) || fontSize,
      };
      if (run?.font_style === "italic") {
        runOpts.italic = true;
      }
      // Break after run when explicit, or when text ends with newline (strip trailing \n).
      let displayText = runText;
      if (displayText.endsWith("\n")) {
        displayText = displayText.slice(0, -1);
        runOpts.breakLine = true;
      } else if (run?.break_line && index < runs.length - 1) {
        runOpts.breakLine = true;
      }
      return { text: displayText, options: runOpts };
    });
    page.addText(payload, opts);
    return;
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
  const mask = String(element.image_mask || "none");
  if (path) {
    const fitMode = element.fit_mode || (element.content_type === "drawing" ? "contain" : "cover");
    // Circle mask: prefer oval shape filled with the image when freeform.
    if (mask === "circle" && !placeholderName && pres.shapes?.OVAL) {
      try {
        page.addShape(pres.shapes.OVAL, {
          x: rect.x,
          y: rect.y,
          w: rect.w,
          h: rect.h,
          fill: { type: "image", path },
          line: { color: "FFFFFF", width: 0 },
        });
        return;
      } catch (_err) {
        // Fall through to rectangular image.
      }
    }
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
      if (element.opacity != null && Number(element.opacity) < 1) {
        opts.transparency = Math.round((1 - Number(element.opacity)) * 100);
      }
    }
    page.addImage(opts);
    // Soft fade: prefer GradientFill bands; legacy gradient_fade fallback.
    // Silhouette no longer fakes a dark gradient — Freeform overlay owns the frame.
    if (!placeholderName && pres.shapes?.RECTANGLE) {
      if (element.fill && Array.isArray(element.fill.stops) && element.fill.stops.length >= 2) {
        _applyGradientApprox(pres, page, rect, element.fill);
      } else if (mask === "gradient_fade") {
        _applyGradientApprox(pres, page, rect, {
          kind: "linear",
          angle_deg: 90,
          stops: [
            { position: 0, color: "1A1A1A", transparency: 1 },
            { position: 0.55, color: "1A1A1A", transparency: 0.85 },
            { position: 1, color: "1A1A1A", transparency: 0.35 },
          ],
        });
      } else if (mask === "silhouette") {
        // Fallback diamond outline when compiler/Studio did not emit a FreeformNode.
        const inset = Math.max(Math.min(rect.w, rect.h) * 0.08, 0.05);
        renderFreeformElement(pres, page, {
          x: rect.x + inset,
          y: rect.y + inset,
          w: Math.max(rect.w - 2 * inset, 0.05),
          h: Math.max(rect.h - 2 * inset, 0.05),
          closed: true,
          stroke_color: "FFFFFF",
          stroke_width: 1.5,
          points: [
            { x: rect.x + rect.w / 2, y: rect.y + inset },
            { x: rect.x + rect.w - inset, y: rect.y + rect.h / 2 },
            { x: rect.x + rect.w / 2, y: rect.y + rect.h - inset },
            { x: rect.x + inset, y: rect.y + rect.h / 2 },
          ],
        });
      }
    }
    return;
  }

  const colors = slideInstruction.theme_tokens?.colors ?? deckTheme?.colors ?? {};
  const fill = _stripHash(colors.surface || colors.light || "F4F6F8");
  const line = _stripHash(colors.warning || colors.accent || colors.primary || "B45309");
  const muted = _stripHash(colors.muted_text || colors.muted || "666666");
  const shapeKind =
    mask === "circle" && pres.shapes?.OVAL ? pres.shapes.OVAL : pres.shapes.RECTANGLE;
  if (!placeholderName) {
    /** @type {Record<string, unknown>} */
    const shapeOpts = {
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
    };
    if (element.corner_radius != null && Number(element.corner_radius) > 0 && mask !== "circle") {
      shapeOpts.rectRadius = Math.min(0.5, Number(element.corner_radius) / Math.max(rect.w, 0.01));
    }
    page.addShape(shapeKind, shapeOpts);
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
  if (mask === "circle") {
    label = `${label} · 圆裁`;
  } else if (mask === "gradient_fade") {
    label = `${label} · 渐隐`;
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
 */
function renderFreeformElement(pres, page, element) {
  const rawPoints = Array.isArray(element.points) ? element.points : [];
  /** @type {{x:number,y:number}[]} */
  const points = rawPoints
    .map((pt) => ({ x: Number(pt?.x) || 0, y: Number(pt?.y) || 0 }))
    .filter((pt) => Number.isFinite(pt.x) && Number.isFinite(pt.y));
  if (points.length < 3 || !pres.shapes?.LINE) {
    return;
  }
  // V1: stroked polyline ring only (not true a:custGeom). Fill is authored
  // on FreeformNode but intentionally not faked as a bounding rect.
  const color = _stripHash(element.stroke_color || element.fill_color || "333333");
  const width = Math.max(Number(element.stroke_width) || 1.0, 0.5);
  const closed = element.closed !== false;
  const segments = closed ? points.length : points.length - 1;
  for (let index = 0; index < segments; index += 1) {
    const start = points[index];
    const end = points[(index + 1) % points.length];
    /** @type {Record<string, unknown>} */
    const lineOpts = {
      x: start.x,
      y: start.y,
      w: end.x - start.x,
      h: end.y - start.y,
      line: { color, width },
    };
    if (element.opacity != null && Number(element.opacity) < 1) {
      lineOpts.transparency = Math.round((1 - Number(element.opacity)) * 100);
    }
    page.addShape(pres.shapes.LINE, lineOpts);
  }
}

/**
 * @param {import('pptxgenjs').default} pres
 * @param {object} page
 * @param {object} element
 */
function renderConnectorElement(pres, page, element) {
  const rawPoints = Array.isArray(element.points) ? element.points : [];
  /** @type {{x:number,y:number}[]} */
  const points = rawPoints
    .map((pt) => ({ x: Number(pt?.x) || 0, y: Number(pt?.y) || 0 }))
    .filter((pt) => Number.isFinite(pt.x) && Number.isFinite(pt.y));
  if (points.length < 2) {
    const x = Number(element.x) || 0;
    const y = Number(element.y) || 0;
    points.push({ x, y }, { x: x + (Number(element.w) || 1), y: y + (Number(element.h) || 0) });
  }
  const color = _stripHash(element.stroke_color || "333333");
  const width = Math.max(Number(element.stroke_width) || 1.5, 0.5);
  const beginArrow = element.arrow_start ? "triangle" : "none";
  const endArrow = element.arrow_end ? "triangle" : "none";
  if (!pres.shapes?.LINE) {
    return;
  }
  for (let index = 0; index < points.length - 1; index += 1) {
    const start = points[index];
    const end = points[index + 1];
    const isLast = index === points.length - 2;
    /** @type {Record<string, unknown>} */
    const lineOpts = {
      x: start.x,
      y: start.y,
      w: end.x - start.x,
      h: end.y - start.y,
      line: {
        color,
        width,
        beginArrowType: index === 0 ? beginArrow : "none",
        endArrowType: isLast ? endArrow : "none",
      },
    };
    if (element.opacity != null && Number(element.opacity) < 1) {
      lineOpts.transparency = Math.round((1 - Number(element.opacity)) * 100);
    }
    page.addShape(pres.shapes.LINE, lineOpts);
  }
  const label = String(element.label || "").trim();
  if (label) {
    const mid = points[Math.floor(points.length / 2)] || points[0];
    page.addText(label, {
      x: mid.x,
      y: mid.y - 0.18,
      w: 1.5,
      h: 0.25,
      fontSize: 10,
      color,
      fontFace: element.font_family_cjk || element.font_family || "Microsoft YaHei",
      align: "center",
    });
  }
}

/**
 * @param {import('pptxgenjs').default} pres
 * @param {object} page
 * @param {object} element
 * @param {object} slideInstruction
 */
function renderShapeElement(pres, page, element, slideInstruction) {
  const colors = slideInstruction.theme_tokens?.colors ?? {};
  const hasFill = Boolean(element.fill_color) || Boolean(element.fill);
  const lineWidth = Number(element.stroke_width) || 0;
  // Stroke-only shapes (e.g. Atmosphere contour rings) must not fall back to a surface fill.
  const strokeOnly = !hasFill && lineWidth > 0;
  const solidFallback = strokeOnly
    ? null
    : _stripHash(
        element.fill_color || colors.surface || colors.light || "F4F6F8",
      );
  const lineColor = _stripHash(
    element.stroke_color || colors.border || colors.muted_text || "D9D5CF",
  );
  const useOval =
    (element.image_mask === "circle" ||
      element.shape_kind === "oval" ||
      element.shape_kind === "ellipse") &&
    pres.shapes?.OVAL;
  const useLine = element.shape_kind === "line" && pres.shapes?.LINE;
  /** @type {Record<string, unknown>} */
  const shapeOpts = {
    x: Number(element.x) || 0,
    y: Number(element.y) || 0,
    w: Number(element.w) || 1,
    h: Number(element.h) || 0.3,
    fill: strokeOnly || useLine ? { type: "none" } : { color: solidFallback || "F4F6F8" },
    line: {
      color: lineColor,
      width: lineWidth > 0 ? lineWidth : useLine ? 1 : 0,
    },
  };
  if (element.opacity != null && Number(element.opacity) < 1) {
    shapeOpts.transparency = Math.round((1 - Number(element.opacity)) * 100);
  }
  let fillMode = "solid";
  if (!strokeOnly && !useLine && element.fill) {
    fillMode = _assignShapeFill(pres, page, shapeOpts, element.fill, solidFallback);
  }
  const shapeType = useLine
    ? pres.shapes.LINE
    : useOval
      ? pres.shapes.OVAL
      : pres.shapes.RECTANGLE;
  page.addShape(shapeType, shapeOpts);
  if (fillMode === "approx" && element.fill && !useLine) {
    _applyGradientApprox(pres, page, {
      x: Number(element.x) || 0,
      y: Number(element.y) || 0,
      w: Number(element.w) || 1,
      h: Number(element.h) || 0.3,
    }, element.fill);
  }
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
