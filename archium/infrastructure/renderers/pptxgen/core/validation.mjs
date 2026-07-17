/** @param {unknown} spec */
export function validatePresentationSpec(spec) {
  if (!spec || typeof spec !== "object") {
    throw new Error("PresentationSpec must be a JSON object");
  }
  if (!Array.isArray(spec.slides)) {
    throw new Error("PresentationSpec.slides must be an array");
  }
  for (const [index, slide] of spec.slides.entries()) {
    if (!slide || typeof slide !== "object") {
      throw new Error(`Slide ${index} must be an object`);
    }
    if (!slide.title || typeof slide.title !== "string") {
      throw new Error(`Slide ${index} is missing title`);
    }
    if (!slide.layout || typeof slide.layout !== "string") {
      throw new Error(`Slide ${index} is missing layout`);
    }
  }
  return spec;
}
