#!/usr/bin/env node
/**
 * Convert LayoutPlan render instructions into a native-element PPTX via PptxGenJS.
 *
 * Executes coordinates from the instruction deck — does not choose layout families.
 *
 * Usage:
 *   node render-plan.mjs --input presentation.layout_instructions.json --output presentation.editable.pptx
 */

import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import pptxgen from "pptxgenjs";
import { applyPlanLayout, renderSlideFromPlan } from "./layouts/from-plan.mjs";

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
    throw new Error(
      "Usage: node render-plan.mjs --input <layout_instructions.json> --output <file.pptx>",
    );
  }
  return args;
}

function validateDeck(raw) {
  if (!raw || typeof raw !== "object") {
    throw new Error("Layout instruction deck must be a JSON object");
  }
  if (!Array.isArray(raw.slides)) {
    throw new Error("Layout instruction deck requires slides[]");
  }
  for (const [index, slide] of raw.slides.entries()) {
    if (!slide || typeof slide !== "object") {
      throw new Error(`slides[${index}] must be an object`);
    }
    if (!Array.isArray(slide.elements)) {
      throw new Error(`slides[${index}].elements must be an array`);
    }
    if (typeof slide.page_width !== "number" || typeof slide.page_height !== "number") {
      throw new Error(`slides[${index}] requires numeric page_width and page_height`);
    }
  }
  return raw;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const inputPath = resolve(args.input);
  const outputPath = resolve(args.output);
  const deck = validateDeck(JSON.parse(readFileSync(inputPath, "utf8")));

  const first = deck.slides[0];
  const tokens = first?.theme_tokens ?? {
    page: { width: first?.page_width ?? 10, height: first?.page_height ?? 5.625 },
    colors: { background: "#FFFFFF" },
  };
  // Prefer explicit page size from first slide instruction.
  tokens.page = {
    ...(tokens.page ?? {}),
    width: first?.page_width ?? tokens.page?.width ?? 10,
    height: first?.page_height ?? tokens.page?.height ?? 5.625,
  };

  const pres = new pptxgen();
  pres.author = "Archium";
  pres.company = "Archium";
  pres.subject = deck.title ?? "Archium Visual Composition";
  pres.title = deck.title ?? "Archium Visual Composition";
  applyPlanLayout(pres, tokens);

  for (const slide of deck.slides) {
    renderSlideFromPlan(pres, slide, deck.theme ?? null);
  }

  await pres.writeFile({ fileName: outputPath });
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exit(1);
});
