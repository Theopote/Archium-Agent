/** @typedef {import('./theme.mjs').PresentationTheme} PresentationTheme */

/** @param {PresentationTheme} theme */
export function contentBox(theme) {
  return {
    x: theme.spacing.marginX,
    y: theme.spacing.marginY + theme.spacing.headerHeight,
    w: theme.slide_size.width - theme.spacing.marginX * 2,
    h: theme.slide_size.height - theme.spacing.marginY * 2 - theme.spacing.headerHeight - 0.35,
  };
}

/** @param {number} count @param {number} totalWidth @param {number} gutter */
export function columnWidth(count, totalWidth, gutter) {
  if (count <= 0) {
    return totalWidth;
  }
  return totalWidth / count - gutter * ((count - 1) / count);
}

/** @param {number} value @param {number} min @param {number} max */
export function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}
