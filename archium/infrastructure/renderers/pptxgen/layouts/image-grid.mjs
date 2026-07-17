import { addContentHeader, addNotes } from "../components/header.mjs";
import { addImageOrPlaceholder, gridRects } from "../core/image-fit.mjs";
import { contentBox } from "../core/geometry.mjs";

/** @param {import('pptxgenjs').default} pres @param {object} slide @param {import('../core/theme.mjs').PresentationTheme} theme */
export function renderImageGridSlide(pres, slide, theme) {
  const page = pres.addSlide({ masterName: "ARCHIUM_MASTER" });
  addContentHeader(pres, page, slide.title, theme);
  const area = contentBox(theme);
  area.y = 1.45;
  area.h = 3.85;
  const placements = gridRects(slide.images ?? [], 2, area);
  for (const { image, rect } of placements) {
    addImageOrPlaceholder(pres, page, image, theme, rect);
  }
  addNotes(page, slide.speaker_notes);
}
