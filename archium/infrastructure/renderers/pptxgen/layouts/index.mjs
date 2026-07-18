import { renderChartSlide } from "./chart.mjs";
import { renderComparisonSlide } from "./comparison.mjs";
import {
  renderBulletsSlide,
  renderClosingSlide,
  renderImageContentSlide,
  renderImageFullSlide,
  renderMessageSlide,
  renderSectionSlide,
  renderThesisSlide,
  renderTimelineSlide,
} from "./content.mjs";
import { renderDataSlide } from "./data.mjs";
import { renderTableSlide } from "./table.mjs";
import { renderImageGridSlide } from "./image-grid.mjs";
import { renderSitePlanSlide } from "./site-plan.mjs";
import { renderTitleSlide } from "./title.mjs";

/** @param {import('pptxgenjs').default} pres @param {object} slide @param {import('../core/theme.mjs').PresentationTheme} theme */
export function renderSlide(pres, slide, theme) {
  switch (slide.layout) {
    case "title":
      renderTitleSlide(pres, slide, theme);
      break;
    case "thesis":
      renderThesisSlide(pres, slide, theme);
      break;
    case "section":
      renderSectionSlide(pres, slide, theme);
      break;
    case "content_bullets":
      renderBulletsSlide(pres, slide, theme);
      break;
    case "content_message":
      renderMessageSlide(pres, slide, theme);
      break;
    case "image_content":
      renderImageContentSlide(pres, slide, theme);
      break;
    case "image_full":
      renderImageFullSlide(pres, slide, theme);
      break;
    case "image_grid":
      renderImageGridSlide(pres, slide, theme);
      break;
    case "site_plan":
      renderSitePlanSlide(pres, slide, theme);
      break;
    case "comparison":
      renderComparisonSlide(pres, slide, theme);
      break;
    case "timeline":
      renderTimelineSlide(pres, slide, theme);
      break;
    case "data":
      renderDataSlide(pres, slide, theme);
      break;
    case "chart":
      renderChartSlide(pres, slide, theme);
      break;
    case "table":
      renderTableSlide(pres, slide, theme);
      break;
    case "closing":
      renderClosingSlide(pres, slide, theme);
      break;
    default:
      renderMessageSlide(pres, slide, theme);
  }
}
