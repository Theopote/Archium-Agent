#!/usr/bin/env node
/**
 * Convert Archium PresentationSpec JSON into an editable PPTX via PptxGenJS.
 *
 * Usage:
 *   node render.mjs --input presentation.spec.json --output presentation.editable.pptx
 */

import { readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import pptxgen from "pptxgenjs";

const COLORS = {
  primary: "1F3A5F",
  accent: "2E6DA4",
  text: "1A1A1A",
  muted: "666666",
  light: "F4F6F8",
  white: "FFFFFF",
};

function parseArgs(argv) {
  const args = { input: null, output: null };
  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (token === "--input") {
      args.input = argv[index + 1];
      index += 1;
    } else if (token === "--output") {
      args.output = argv[index + 1];
      index += 1;
    }
  }
  if (!args.input || !args.output) {
    throw new Error("Usage: node render.mjs --input <spec.json> --output <file.pptx>");
  }
  return args;
}

function addTitleSlide(pres, slide) {
  const page = pres.addSlide({ masterName: "ARCHIUM_MASTER" });
  page.background = { color: COLORS.primary };
  page.addText(slide.title, {
    x: 0.7,
    y: 1.8,
    w: 8.6,
    h: 1.2,
    fontSize: 34,
    bold: true,
    color: COLORS.white,
    fontFace: "Microsoft YaHei",
  });
  if (slide.subtitle) {
    page.addText(slide.subtitle, {
      x: 0.7,
      y: 3.1,
      w: 8.6,
      h: 0.6,
      fontSize: 18,
      color: "D9E2EF",
      fontFace: "Microsoft YaHei",
    });
  }
  if (slide.message) {
    page.addText(slide.message, {
      x: 0.7,
      y: 4.0,
      w: 8.6,
      h: 1.0,
      fontSize: 16,
      color: "EAF0F7",
      fontFace: "Microsoft YaHei",
    });
  }
  addNotes(page, slide.speaker_notes);
}

function addThesisSlide(pres, slide) {
  const page = pres.addSlide({ masterName: "ARCHIUM_MASTER" });
  page.addText(slide.title, {
    x: 0.7,
    y: 0.5,
    w: 8.6,
    h: 0.6,
    fontSize: 24,
    bold: true,
    color: COLORS.primary,
    fontFace: "Microsoft YaHei",
  });
  if (slide.message) {
    page.addShape(pres.shapes.RECTANGLE, {
      x: 0.7,
      y: 1.4,
      w: 8.6,
      h: 3.8,
      fill: { color: COLORS.light },
      line: { color: COLORS.light },
    });
    page.addText(slide.message, {
      x: 1.0,
      y: 1.7,
      w: 8.0,
      h: 3.2,
      fontSize: 22,
      color: COLORS.text,
      fontFace: "Microsoft YaHei",
      valign: "mid",
    });
  }
  addNotes(page, slide.speaker_notes);
}

function addSectionSlide(pres, slide) {
  const page = pres.addSlide({ masterName: "ARCHIUM_MASTER" });
  page.background = { color: COLORS.accent };
  page.addText(slide.title, {
    x: 0.7,
    y: 2.2,
    w: 8.6,
    h: 1.0,
    fontSize: 30,
    bold: true,
    color: COLORS.white,
    fontFace: "Microsoft YaHei",
    align: "center",
  });
  if (slide.subtitle) {
    page.addText(slide.subtitle, {
      x: 0.7,
      y: 3.3,
      w: 8.6,
      h: 0.8,
      fontSize: 16,
      color: "EAF0F7",
      fontFace: "Microsoft YaHei",
      align: "center",
    });
  }
  addNotes(page, slide.speaker_notes);
}

function addContentHeader(page, title) {
  page.addText(title, {
    x: 0.7,
    y: 0.45,
    w: 8.6,
    h: 0.7,
    fontSize: 24,
    bold: true,
    color: COLORS.primary,
    fontFace: "Microsoft YaHei",
  });
  page.addShape("rect", {
    x: 0.7,
    y: 1.15,
    w: 1.2,
    h: 0.06,
    fill: { color: COLORS.accent },
    line: { color: COLORS.accent },
  });
}

function addBulletsSlide(pres, slide) {
  const page = pres.addSlide({ masterName: "ARCHIUM_MASTER" });
  addContentHeader(page, slide.title);
  if (slide.message) {
    page.addText(slide.message, {
      x: 0.7,
      y: 1.35,
      w: 8.6,
      h: 0.8,
      fontSize: 16,
      bold: true,
      color: COLORS.text,
      fontFace: "Microsoft YaHei",
    });
  }
  if (slide.bullets.length > 0) {
    page.addText(
      slide.bullets.map((item) => ({ text: item, options: { bullet: true, breakLine: true } })),
      {
        x: 0.9,
        y: slide.message ? 2.2 : 1.5,
        w: 8.2,
        h: 3.8,
        fontSize: 16,
        color: COLORS.text,
        fontFace: "Microsoft YaHei",
      },
    );
  }
  addNotes(page, slide.speaker_notes);
}

function addMessageSlide(pres, slide) {
  const page = pres.addSlide({ masterName: "ARCHIUM_MASTER" });
  addContentHeader(page, slide.title);
  if (slide.message) {
    page.addText(slide.message, {
      x: 0.7,
      y: 1.5,
      w: 8.6,
      h: 3.8,
      fontSize: 20,
      color: COLORS.text,
      fontFace: "Microsoft YaHei",
      valign: "top",
    });
  }
  addNotes(page, slide.speaker_notes);
}

function addImageContentSlide(pres, slide) {
  const page = pres.addSlide({ masterName: "ARCHIUM_MASTER" });
  addContentHeader(page, slide.title);
  const textWidth = slide.images.length > 0 ? 4.8 : 8.6;
  if (slide.message) {
    page.addText(slide.message, {
      x: 0.7,
      y: 1.4,
      w: textWidth,
      h: 0.9,
      fontSize: 16,
      bold: true,
      color: COLORS.text,
      fontFace: "Microsoft YaHei",
    });
  }
  if (slide.bullets.length > 0) {
    page.addText(
      slide.bullets.map((item) => ({ text: item, options: { bullet: true, breakLine: true } })),
      {
        x: 0.9,
        y: slide.message ? 2.3 : 1.5,
        w: textWidth - 0.2,
        h: 3.5,
        fontSize: 15,
        color: COLORS.text,
        fontFace: "Microsoft YaHei",
      },
    );
  }
  for (const image of slide.images) {
    if (image.asset_path) {
      page.addImage({
        path: image.asset_path,
        x: image.x ?? 5.0,
        y: image.y ?? 1.5,
        w: image.w ?? 4.0,
        h: image.h ?? 3.5,
      });
    } else {
      page.addShape("rect", {
        x: image.x ?? 5.0,
        y: image.y ?? 1.5,
        w: image.w ?? 4.0,
        h: image.h ?? 3.5,
        fill: { color: COLORS.light },
        line: { color: COLORS.accent, width: 1 },
      });
      page.addText(image.description, {
        x: (image.x ?? 5.0) + 0.2,
        y: (image.y ?? 1.5) + 1.4,
        w: (image.w ?? 4.0) - 0.4,
        h: 0.8,
        fontSize: 12,
        color: COLORS.muted,
        fontFace: "Microsoft YaHei",
        align: "center",
      });
    }
  }
  addNotes(page, slide.speaker_notes);
}

function addClosingSlide(pres, slide) {
  const page = pres.addSlide({ masterName: "ARCHIUM_MASTER" });
  page.background = { color: COLORS.primary };
  page.addText(slide.title, {
    x: 0.7,
    y: 2.0,
    w: 8.6,
    h: 1.0,
    fontSize: 28,
    bold: true,
    color: COLORS.white,
    fontFace: "Microsoft YaHei",
    align: "center",
  });
  if (slide.message) {
    page.addText(slide.message, {
      x: 0.7,
      y: 3.1,
      w: 8.6,
      h: 1.2,
      fontSize: 18,
      color: "EAF0F7",
      fontFace: "Microsoft YaHei",
      align: "center",
    });
  }
  addNotes(page, slide.speaker_notes);
}

function addNotes(page, notes) {
  if (notes) {
    page.addNotes(notes);
  }
}

function renderSlide(pres, slide) {
  switch (slide.layout) {
    case "title":
      addTitleSlide(pres, slide);
      break;
    case "thesis":
      addThesisSlide(pres, slide);
      break;
    case "section":
      addSectionSlide(pres, slide);
      break;
    case "content_bullets":
      addBulletsSlide(pres, slide);
      break;
    case "content_message":
      addMessageSlide(pres, slide);
      break;
    case "image_content":
      addImageContentSlide(pres, slide);
      break;
    case "closing":
      addClosingSlide(pres, slide);
      break;
    default:
      addMessageSlide(pres, slide);
  }
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const inputPath = resolve(args.input);
  const outputPath = resolve(args.output);
  const spec = JSON.parse(readFileSync(inputPath, "utf8"));

  const pres = new pptxgen();
  pres.layout = "LAYOUT_16x9";
  pres.author = "Archium";
  pres.company = "Archium";
  pres.subject = spec.title ?? "Archium Presentation";
  pres.title = spec.title ?? "Archium Presentation";

  pres.defineSlideMaster({
    title: "ARCHIUM_MASTER",
    background: { color: COLORS.white },
    slideNumber: { x: 9.0, y: 5.35, color: COLORS.muted, fontSize: 10 },
  });

  for (const slide of spec.slides ?? []) {
    renderSlide(pres, slide);
  }

  await pres.writeFile({ fileName: outputPath });
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exit(1);
});
