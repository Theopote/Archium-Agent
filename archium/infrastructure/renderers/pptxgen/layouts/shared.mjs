import { addContentHeader, addFooter, addNotes } from "../components/header.mjs";
import { addCitationBlock } from "../components/citation.mjs";
import { bulletRuns, textOptions } from "../core/text-fit.mjs";

/**
 * Render citation lines at the bottom of a content slide (layout-family path).
 * @param {object} page
 * @param {object} slide
 * @param {import('../core/theme.mjs').PresentationTheme} theme
 */
function addSlideCitations(page, slide, theme) {
  const lines = Array.isArray(slide?.citations)
    ? slide.citations.map((item) => String(item || "").trim()).filter(Boolean)
    : Array.isArray(slide?.source_citations)
      ? slide.source_citations
          .map((item) => {
            if (typeof item === "string") return item.trim();
            const name = String(item?.document_name || "").trim();
            if (!name) return "";
            const pageNo = item?.page_number ? ` p.${item.page_number}` : "";
            return `${name}${pageNo}`;
          })
          .filter(Boolean)
      : [];
  if (!lines.length) {
    return;
  }
  const marginX = theme?.spacing?.marginX ?? 0.5;
  const width = (theme?.slide_size?.width ?? 10) - marginX * 2;
  const height = theme?.slide_size?.height ?? 5.625;
  addCitationBlock(page, lines.slice(0, 4), theme, {
    x: marginX,
    y: height - 0.85,
    w: width,
    h: 0.7,
  });
}

export {
  addContentHeader,
  addFooter,
  addNotes,
  addSlideCitations,
  bulletRuns,
  textOptions,
};
