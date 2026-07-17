/** @typedef {import('./theme.mjs').PresentationTheme} PresentationTheme */

/** @param {string[]} bullets */
export function bulletRuns(bullets) {
  return bullets.map((item) => ({ text: item, options: { bullet: true, breakLine: true } }));
}

/** @param {PresentationTheme} theme @param {'heading'|'body'|'caption'} role @param {object} extra */
export function textOptions(theme, role, extra = {}) {
  const fontFace = role === "caption" ? theme.fonts.caption : theme.fonts.body;
  const style =
    role === "heading"
      ? theme.component_styles.header
      : role === "caption"
        ? theme.component_styles.caption
        : theme.component_styles.body;
  return {
    fontFace,
    fontSize: style.fontSize,
    bold: Boolean(style.bold),
    color: theme.colors.text,
    ...extra,
  };
}
