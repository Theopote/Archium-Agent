/** @typedef {import('./theme.mjs').PresentationTheme} PresentationTheme */

/**
 * @param {{ asset_path?: string | null, description?: string, x?: number, y?: number, w?: number, h?: number }} image
 * @param {{ x: number, y: number, w: number, h: number }} fallback
 */
export function imageRect(image, fallback) {
  return {
    x: image.x ?? fallback.x,
    y: image.y ?? fallback.y,
    w: image.w ?? fallback.w,
    h: image.h ?? fallback.h,
  };
}

/** @param {import('pptxgenjs').default} pres @param {object} page @param {object} image @param {PresentationTheme} theme @param {object} rect */
export function addImageOrPlaceholder(pres, page, image, theme, rect) {
  if (image.asset_path) {
    page.addImage({
      path: image.asset_path,
      x: rect.x,
      y: rect.y,
      w: rect.w,
      h: rect.h,
    });
    return;
  }
  page.addShape("rect", {
    x: rect.x,
    y: rect.y,
    w: rect.w,
    h: rect.h,
    fill: { color: theme.colors.light },
    line: { color: theme.colors.accent, width: 1 },
  });
  page.addText(image.description ?? "图片占位", {
    x: rect.x + 0.2,
    y: rect.y + rect.h / 2 - 0.4,
    w: rect.w - 0.4,
    h: 0.8,
    fontSize: theme.component_styles.caption.fontSize,
    color: theme.colors.muted,
    fontFace: theme.fonts.caption,
    align: "center",
  });
}

/** @param {Array<object>} images @param {number} columns @param {object} area */
export function gridRects(images, columns, area) {
  const count = Math.max(images.length, 1);
  const cols = Math.min(columns, count);
  const rows = Math.ceil(count / cols);
  const cellW = area.w / cols - 0.15;
  const cellH = area.h / rows - 0.15;
  return images.map((image, index) => {
    const col = index % cols;
    const row = Math.floor(index / cols);
    return {
      image,
      rect: {
        x: area.x + col * (cellW + 0.15),
        y: area.y + row * (cellH + 0.15),
        w: cellW,
        h: cellH,
      },
    };
  });
}
