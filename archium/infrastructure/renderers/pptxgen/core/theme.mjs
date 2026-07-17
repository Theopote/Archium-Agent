/** @typedef {import('pptxgenjs').default} PptxGen */

/**
 * @typedef PresentationTheme
 * @property {string} name
 * @property {{ heading: string, body: string, caption: string }} fonts
 * @property {Record<string, string>} colors
 * @property {{ marginX: number, marginY: number, gutter: number, headerHeight: number }} spacing
 * @property {{ width: number, height: number, layout: string }} slide_size
 * @property {{ enabled: boolean, path: string | null, x: number, y: number, w: number, h: number }} logo
 * @property {{ enabled: boolean, text: string, x: number, y: number, w: number, h: number, fontSize: number }} footer
 * @property {{ enabled: boolean, x: number, y: number, fontSize: number, color: string }} page_number
 * @property {Record<string, object>} component_styles
 */

const BASE = {
  fonts: {
    heading: "Microsoft YaHei",
    body: "Microsoft YaHei",
    caption: "Microsoft YaHei",
  },
  spacing: {
    marginX: 0.7,
    marginY: 0.45,
    gutter: 0.4,
    headerHeight: 0.7,
  },
  slide_size: {
    width: 10,
    height: 5.625,
    layout: "LAYOUT_16x9",
  },
  logo: {
    enabled: false,
    path: null,
    x: 8.8,
    y: 0.2,
    w: 0.8,
    h: 0.35,
  },
  footer: {
    enabled: false,
    text: "",
    x: 0.7,
    y: 5.2,
    w: 8.6,
    h: 0.25,
    fontSize: 9,
  },
  page_number: {
    enabled: true,
    x: 9.0,
    y: 5.35,
    fontSize: 10,
    color: "666666",
  },
  component_styles: {
    title: { fontSize: 34, bold: true },
    section: { fontSize: 30, bold: true },
    header: { fontSize: 24, bold: true },
    body: { fontSize: 16 },
    caption: { fontSize: 12 },
    metric: { fontSize: 22, bold: true },
  },
};

/** @param {string} name @param {Partial<PresentationTheme>} overrides */
function buildTheme(name, overrides) {
  return {
    name,
    fonts: { ...BASE.fonts, ...(overrides.fonts ?? {}) },
    colors: { ...overrides.colors },
    spacing: { ...BASE.spacing, ...(overrides.spacing ?? {}) },
    slide_size: { ...BASE.slide_size, ...(overrides.slide_size ?? {}) },
    logo: { ...BASE.logo, ...(overrides.logo ?? {}) },
    footer: { ...BASE.footer, ...(overrides.footer ?? {}) },
    page_number: { ...BASE.page_number, ...(overrides.page_number ?? {}) },
    component_styles: { ...BASE.component_styles, ...(overrides.component_styles ?? {}) },
  };
}

/** @type {Record<string, PresentationTheme>} */
export const THEMES = {
  "minimal-light": buildTheme("minimal-light", {
    colors: {
      primary: "111111",
      accent: "444444",
      text: "1A1A1A",
      muted: "777777",
      light: "F5F5F5",
      white: "FFFFFF",
      onPrimary: "FFFFFF",
      subtitle: "666666",
    },
  }),
  "minimal-dark": buildTheme("minimal-dark", {
    colors: {
      primary: "101820",
      accent: "5B6770",
      text: "F2F4F7",
      muted: "B8C0CC",
      light: "1E2630",
      white: "FFFFFF",
      onPrimary: "FFFFFF",
      subtitle: "D0D7E2",
    },
    page_number: { enabled: true, x: 9.0, y: 5.35, fontSize: 10, color: "B8C0CC" },
  }),
  "architecture-board": buildTheme("architecture-board", {
    colors: {
      primary: "1F3A5F",
      accent: "2E6DA4",
      text: "1A1A1A",
      muted: "666666",
      light: "F4F6F8",
      white: "FFFFFF",
      onPrimary: "FFFFFF",
      subtitle: "D9E2EF",
    },
  }),
  "government-review": buildTheme("government-review", {
    colors: {
      primary: "8B1A1A",
      accent: "B8860B",
      text: "222222",
      muted: "666666",
      light: "FAF6F0",
      white: "FFFFFF",
      onPrimary: "FFFFFF",
      subtitle: "F0E6D8",
    },
    footer: {
      enabled: true,
      text: "汇报材料 · 仅供评审",
      x: 0.7,
      y: 5.15,
      w: 8.6,
      h: 0.25,
      fontSize: 9,
    },
  }),
  competition: buildTheme("competition", {
    colors: {
      primary: "0B0B0B",
      accent: "E4572E",
      text: "111111",
      muted: "555555",
      light: "F0F0F0",
      white: "FFFFFF",
      onPrimary: "FFFFFF",
      subtitle: "CCCCCC",
    },
    component_styles: {
      title: { fontSize: 38, bold: true },
      section: { fontSize: 32, bold: true },
      header: { fontSize: 26, bold: true },
      body: { fontSize: 17 },
      caption: { fontSize: 12 },
      metric: { fontSize: 24, bold: true },
    },
  }),
  "technical-review": buildTheme("technical-review", {
    colors: {
      primary: "2F4F4F",
      accent: "3A7CA5",
      text: "1C1C1C",
      muted: "5A5A5A",
      light: "EEF2F4",
      white: "FFFFFF",
      onPrimary: "FFFFFF",
      subtitle: "D5DEE5",
    },
    fonts: {
      heading: "Arial",
      body: "Arial",
      caption: "Arial",
    },
  }),
};

const ALIASES = {
  "archium-default": "architecture-board",
  default: "architecture-board",
};

/** @param {string | undefined | null} name @returns {PresentationTheme} */
export function resolveTheme(name) {
  const key = ALIASES[name ?? ""] ?? name ?? "architecture-board";
  return THEMES[key] ?? THEMES["architecture-board"];
}

/** @param {PptxGen} pres @param {PresentationTheme} theme */
export function defineSlideMaster(pres, theme) {
  pres.layout = theme.slide_size.layout;
  pres.defineSlideMaster({
    title: "ARCHIUM_MASTER",
    background: { color: theme.colors.white },
    slideNumber: theme.page_number.enabled
      ? {
          x: theme.page_number.x,
          y: theme.page_number.y,
          color: theme.page_number.color,
          fontSize: theme.page_number.fontSize,
        }
      : undefined,
  });
}

export const THEME_NAMES = Object.keys(THEMES);
