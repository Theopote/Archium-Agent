import { addContentHeader, addNotes } from "../components/header.mjs";
import { addImageOrPlaceholder } from "../core/image-fit.mjs";
import { addLegend } from "../components/legend.mjs";
import { addNorthArrow } from "../components/north-arrow.mjs";
import { addScaleBar } from "../components/scale-bar.mjs";

/** @param {import('pptxgenjs').default} pres @param {object} slide @param {import('../core/theme.mjs').PresentationTheme} theme */
export function renderSitePlanSlide(pres, slide, theme) {
  const page = pres.addSlide({ masterName: "ARCHIUM_MASTER" });
  addContentHeader(pres, page, slide.title, theme);
  const image = (slide.images ?? [])[0];
  const rect = { x: theme.spacing.marginX, y: 1.45, w: 8.6, h: 3.85 };
  if (image) {
    addImageOrPlaceholder(pres, page, image, theme, rect);
  }
  addNorthArrow(page, theme, { x: rect.x + rect.w - 0.5, y: rect.y + 0.15 });
  addScaleBar(page, theme, { x: rect.x + 0.2, y: rect.y + rect.h - 0.35, w: 1.5, label: "0 — 50m" });
  addLegend(page, [{ label: "人行", color: theme.colors.accent }, { label: "车行", color: theme.colors.primary }], theme, {
    x: rect.x + rect.w - 1.5,
    y: rect.y + rect.h - 0.9,
    w: 1.3,
    h: 0.8,
  });
  if (slide.message) {
    page.addText(slide.message, {
      x: theme.spacing.marginX,
      y: 5.05,
      w: theme.slide_size.width - theme.spacing.marginX * 2,
      h: 0.45,
      fontSize: 13,
      color: theme.colors.muted,
      fontFace: theme.fonts.body,
      align: "center",
    });
  }
  addNotes(page, slide.speaker_notes);
}
