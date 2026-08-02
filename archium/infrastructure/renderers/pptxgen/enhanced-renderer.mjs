#!/usr/bin/env node
/**
 * Enhanced PptxGenJS renderer with professional design system integration.
 * 
 * This module provides advanced rendering capabilities including:
 * - Gradient fills and advanced effects
 * - Typography system integration
 * - Visual elements library support
 * - Design token application
 * - Professional quality output
 */

import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import pptxgen from "pptxgenjs";

/**
 * Design System Integration
 * Applies professional design tokens to PowerPoint elements
 */
class DesignSystemRenderer {
  constructor(designSystem) {
    this.designSystem = designSystem || this.getDefaultDesignSystem();
  }

  getDefaultDesignSystem() {
    return {
      colors: {
        primary: "#0EA5E9",
        secondary: "#64748B",
        accent: "#F59E0B",
        neutral: "#F1F5F9",
        success: "#10B981",
        warning: "#F59E0B",
        error: "#EF4444",
        info: "#3B82F6"
      },
      typography: {
        fontFamily: "Arial",
        fontSizes: {
          h1: 36,
          h2: 28,
          h3: 24,
          h4: 20,
          body: 14,
          small: 12
        },
        lineHeights: {
          tight: 1.2,
          normal: 1.5,
          relaxed: 1.8
        }
      },
      spacing: {
        xs: 4,
        sm: 8,
        md: 16,
        lg: 24,
        xl: 32,
        xxl: 48
      },
      effects: {
        shadow: {
          light: "rgba(0,0,0,0.1)",
          medium: "rgba(0,0,0,0.2)",
          dark: "rgba(0,0,0,0.3)"
        },
        borderRadius: {
          sm: 2,
          md: 4,
          lg: 8,
          xl: 12,
          full: 9999
        }
      }
    };
  }

  /**
   * Apply gradient fill to a shape
   */
  applyGradientFill(shape, gradientConfig) {
    const { type = "linear", colors = [], angle = 90 } = gradientConfig;
    
    if (type === "linear") {
      shape.fill = {
        type: "gradient",
        colors: colors.map((c, i) => ({
          color: c,
          position: i / (colors.length - 1)
        })),
        angle: angle
      };
    } else if (type === "radial") {
      shape.fill = {
        type: "radialGradient",
        colors: colors
      };
    }
    
    return shape;
  }

  /**
   * Apply shadow effect to a shape
   */
  applyShadow(shape, shadowConfig) {
    const { 
      type = "outer", 
      color = this.designSystem.effects.shadow.medium,
      blur = 5,
      offset = { x: 2, y: 2 },
      transparency = 20
    } = shadowConfig;
    
    shape.shadow = {
      type: type,
      color: color.replace("rgba", "rgb").replace(/[\d.]+\)$/, `${transparency / 100})`),
      blur: blur,
      offset: offset
    };
    
    return shape;
  }

  /**
   * Apply transparency to a shape
   */
  applyTransparency(shape, transparency) {
    shape.options = { ...(shape.options || {}), transparency: transparency };
    return shape;
  }

  /**
   * Apply border radius to a shape
   */
  applyBorderRadius(shape, radius) {
    const radiusMap = this.designSystem.effects.borderRadius;
    const actualRadius = radiusMap[radius] || radius || 0;
    shape.options = { ...(shape.options || {}), borderRadius: actualRadius };
    return shape;
  }

  /**
   * Apply typography styling to text
   */
  applyTypography(text, typographyConfig) {
    const {
      fontSize = this.designSystem.typography.fontSizes.body,
      fontFamily = this.designSystem.typography.fontFamily,
      color = this.designSystem.colors.neutral,
      bold = false,
      italic = false,
      underline = false
    } = typographyConfig;

    text.options = {
      ...text.options,
      fontSize: fontSize,
      fontFamily: fontFamily,
      color: color.replace("#", ""),
      bold: bold,
      italic: italic,
      underline: underline
    };

    return text;
  }

  /**
   * Apply design system colors to elements
   */
  applyColorScheme(elements, colorScheme) {
    const colors = this.designSystem.colors;
    
    return elements.map(element => {
      if (element.type === "shape" || element.type === "text") {
        if (element.colorRole === "primary") {
          element.color = colors.primary;
        } else if (element.colorRole === "secondary") {
          element.color = colors.secondary;
        } else if (element.colorRole === "accent") {
          element.color = colors.accent;
        } else if (element.colorRole === "neutral") {
          element.color = colors.neutral;
        }
      }
      return element;
    });
  }
}

/**
 * Advanced Effects Renderer
 * Handles complex visual effects for professional presentations
 */
class AdvancedEffectsRenderer {
  constructor(presentation) {
    this.pres = presentation;
  }

  /**
   * Create a glassmorphism effect
   */
  createGlassmorphism(x, y, w, h, config = {}) {
    const {
      backgroundColor = "rgba(255, 255, 255, 0.8)",
      borderColor = "rgba(255, 255, 255, 0.5)",
      borderWidth = 1,
      blur = 10,
      shadow = true
    } = config;

    const shape = this.pres.addShape(pres.ShapeType.rect, {
      x: x,
      y: y,
      w: w,
      h: h,
      fill: { color: backgroundColor },
      line: { color: borderColor, width: borderWidth }
    });

    if (shadow) {
      shape.shadow = {
        type: "outer",
        color: "rgba(0, 0, 0, 0.1)",
        blur: blur,
        offset: { x: 0, y: 4 }
      };
    }

    return shape;
  }

  /**
   * Create a card with elevated shadow
   */
  createCard(x, y, w, h, config = {}) {
    const {
      backgroundColor = "#FFFFFF",
      elevation = "md",
      borderRadius = 8
    } = config;

    const elevationMap = {
      xs: { blur: 2, offset: { x: 1, y: 1 }, transparency: 5 },
      sm: { blur: 4, offset: { x: 2, y: 2 }, transparency: 10 },
      md: { blur: 6, offset: { x: 2, y: 4 }, transparency: 15 },
      lg: { blur: 10, offset: { x: 4, y: 6 }, transparency: 20 },
      xl: { blur: 15, offset: { x: 6, y: 8 }, transparency: 25 }
    };

    const elevationConfig = elevationMap[elevation] || elevationMap.md;

    const shape = this.pres.addShape(pres.ShapeType.rect, {
      x: x,
      y: y,
      w: w,
      h: h,
      fill: { color: backgroundColor },
      options: { borderRadius: borderRadius }
    });

    shape.shadow = {
      type: "outer",
      color: "rgba(0, 0, 0, 0.1)",
      blur: elevationConfig.blur,
      offset: elevationConfig.offset
    };

    return shape;
  }

  /**
   * Create a gradient background
   */
  createGradientBackground(slide, gradientConfig) {
    const {
      type = "linear",
      colors = ["#0EA5E9", "#0369A1"],
      angle = 135
    } = gradientConfig;

    slide.background = {
      fill: {
        type: "gradient",
        colors: colors.map((c, i) => ({
          color: c,
          position: i / (colors.length - 1)
        })),
        angle: angle
      }
    };

    return slide;
  }

  /**
   * Create a pattern overlay
   */
  createPatternOverlay(x, y, w, h, patternConfig) {
    const {
      pattern = "dots",
      color = "rgba(0, 0, 0, 0.1)",
      size = 10
    } = patternConfig;

    // PptxGenJS has limited pattern support, so we create a simplified version
    const shape = this.pres.addShape(pres.ShapeType.rect, {
      x: x,
      y: y,
      w: w,
      h: h,
      fill: { color: "transparent" },
      line: { color: color, width: 0.5, dash: "dash" }
    });

    return shape;
  }

  /**
   * Create a divider line with style
   */
  createDivider(x, y, w, style = "solid") {
    const line = this.pres.addShape(pres.ShapeType.line, {
      x: x,
      y: y,
      w: w,
      h: 0,
      line: { color: "#64748B", width: 1, dash: style === "dashed" ? "dash" : "solid" }
    });

    return line;
  }
}

/**
 * Typography Renderer
 * Advanced text rendering with proper hierarchy
 */
class TypographyRenderer {
  constructor(presentation, designSystem) {
    this.pres = presentation;
    this.designSystem = designSystem;
  }

  /**
   * Add heading with proper styling
   */
  addHeading(text, level = 1, config = {}) {
    const {
      x = 0.5,
      y = 0.5,
      w = 9,
      h = 1,
      color = this.designSystem.colors.primary,
      align = "left",
      fontSize = this.designSystem.typography.fontSizes[`h${level}`] || 24
    } = config;

    return this.pres.addText(text, {
      x: x,
      y: y,
      w: w,
      h: h,
      fontSize: fontSize,
      color: color.replace("#", ""),
      bold: true,
      align: align,
      fontFamily: this.designSystem.typography.fontFamily
    });
  }

  /**
   * Add body text with proper styling
   */
  addBodyText(text, config = {}) {
    const {
      x = 0.5,
      y = 2,
      w = 9,
      h = 4,
      color = this.designSystem.colors.neutral,
      fontSize = this.designSystem.typography.fontSizes.body,
      lineSpacing = this.designSystem.typography.lineHeights.normal
    } = config;

    return this.pres.addText(text, {
      x: x,
      y: y,
      w: w,
      h: h,
      fontSize: fontSize,
      color: color.replace("#", ""),
      align: "left",
      fontFamily: this.designSystem.typography.fontFamily,
      lineSpacing: lineSpacing
    });
  }

  /**
   * Add styled bullet points
   */
  addBulletPoints(items, config = {}) {
    const {
      x = 0.5,
      y = 2,
      w = 9,
      h = 4,
      color = this.designSystem.colors.neutral,
      fontSize = this.designSystem.typography.fontSizes.body,
      bulletColor = this.designSystem.colors.primary
    } = config;

    const bulletText = items.map(item => ({ 
      text: item, 
      options: { 
        bullet: { 
          color: bulletColor.replace("#", "") 
        } 
      } 
    }));

    return this.pres.addText(bulletText, {
      x: x,
      y: y,
      w: w,
      h: h,
      fontSize: fontSize,
      color: color.replace("#", ""),
      align: "left",
      fontFamily: this.designSystem.typography.fontFamily
    });
  }

  /**
   * Add quote with styling
   */
  addQuote(text, attribution, config = {}) {
    const {
      x = 1,
      y = 2,
      w = 8,
      h = 3,
      color = this.designSystem.colors.secondary,
      fontSize = this.designSystem.typography.fontSizes.h3
    } = config;

    this.pres.addText(`"${text}"`, {
      x: x,
      y: y,
      w: w,
      h: h * 0.7,
      fontSize: fontSize,
      color: color.replace("#", ""),
      italic: true,
      align: "center",
      fontFamily: this.designSystem.typography.fontFamily
    });

    if (attribution) {
      this.pres.addText(`— ${attribution}`, {
        x: x,
        y: y + h * 0.8,
        w: w,
        h: h * 0.2,
        fontSize: this.designSystem.typography.fontSizes.small,
        color: this.designSystem.colors.neutral.replace("#", ""),
        align: "right",
        fontFamily: this.designSystem.typography.fontFamily
      });
    }
  }
}

/**
 * Main Enhanced Renderer
 * Coordinates all rendering components
 */
class EnhancedRenderer {
  constructor(presentation, designSystem = null) {
    this.pres = presentation;
    this.designSystemRenderer = new DesignSystemRenderer(designSystem);
    this.effectsRenderer = new AdvancedEffectsRenderer(presentation);
    this.typographyRenderer = new TypographyRenderer(presentation, designSystem);
  }

  /**
   * Apply professional design system to presentation
   */
  applyDesignSystem(designSystem) {
    this.designSystemRenderer = new DesignSystemRenderer(designSystem);
    this.typographyRenderer = new TypographyRenderer(this.pres, designSystem);
    
    // Apply design system to slide master
    this.applySlideMaster(designSystem);
  }

  /**
   * Apply design system to slide master
   */
  applySlideMaster(designSystem) {
    this.pres.layout = "LAYOUT_16x9";
    
    // Define master slide with design system colors
    this.pres.defineSlideMaster({
      title: designSystem.colors.primary.replace("#", ""),
      body: {
        color: designSystem.colors.neutral.replace("#", "")
      }
    });
  }

  /**
   * Render a professionally styled slide
   */
  renderProfessionalSlide(slideData) {
    const { type, content, style } = slideData;

    switch (type) {
      case "title":
        this.renderTitleSlide(content, style);
        break;
      case "content":
        this.renderContentSlide(content, style);
        break;
      case "two_column":
        this.renderTwoColumnSlide(content, style);
        break;
      case "image_text":
        this.renderImageTextSlide(content, style);
        break;
      case "chart":
        this.renderChartSlide(content, style);
        break;
      default:
        this.renderContentSlide(content, style);
    }
  }

  /**
   * Render title slide
   */
  renderTitleSlide(content, style) {
    const { title, subtitle, backgroundImage } = content;
    
    if (backgroundImage) {
      this.pres.addImage({
        path: backgroundImage,
        x: 0,
        y: 0,
        w: "100%",
        h: "100%"
      });
    }

    this.typographyRenderer.addHeading(title, 1, {
      x: 0.5,
      y: 3,
      w: 9,
      h: 1.5,
      align: "center",
      color: style?.titleColor || this.designSystemRenderer.designSystem.colors.primary
    });

    if (subtitle) {
      this.typographyRenderer.addBodyText(subtitle, {
        x: 0.5,
        y: 4.5,
        w: 9,
        h: 1,
        align: "center",
        fontSize: 18
      });
    }
  }

  /**
   * Render content slide
   */
  renderContentSlide(content, style) {
    const { title, body, bullets } = content;

    this.typographyRenderer.addHeading(title, 2, {
      y: 0.5,
      color: style?.titleColor
    });

    if (bullets && bullets.length > 0) {
      this.typographyRenderer.addBulletPoints(bullets, {
        y: 1.5
      });
    } else if (body) {
      this.typographyRenderer.addBodyText(body, {
        y: 1.5
      });
    }
  }

  /**
   * Render two column slide
   */
  renderTwoColumnSlide(content, style) {
    const { title, leftContent, rightContent } = content;

    this.typographyRenderer.addHeading(title, 2, {
      y: 0.5
    });

    // Add divider
    this.effectsRenderer.createDivider(5, 1.3, 0, "solid");

    // Left column
    if (leftContent.text) {
      this.typographyRenderer.addBodyText(leftContent.text, {
        x: 0.5,
        y: 1.5,
        w: 4
      });
    }

    // Right column
    if (rightContent.text) {
      this.typographyRenderer.addBodyText(rightContent.text, {
        x: 5.5,
        y: 1.5,
        w: 4
      });
    }
  }

  /**
   * Render image-text slide
   */
  renderImageTextSlide(content, style) {
    const { title, image, text, imagePosition = "left" } = content;

    this.typographyRenderer.addHeading(title, 2, {
      y: 0.5
    });

    if (imagePosition === "left") {
      this.pres.addImage({
        path: image,
        x: 0.5,
        y: 1.5,
        w: 5,
        h: 4
      });

      if (text) {
        this.typographyRenderer.addBodyText(text, {
          x: 5.5,
          y: 1.5,
          w: 4
        });
      }
    } else {
      if (text) {
        this.typographyRenderer.addBodyText(text, {
          x: 0.5,
          y: 1.5,
          w: 4
        });
      }

      this.pres.addImage({
        path: image,
        x: 5.5,
        y: 1.5,
        w: 5,
        h: 4
      });
    }
  }

  /**
   * Render chart slide
   */
  renderChartSlide(content, style) {
    const { title, chartData, chartType } = content;

    this.typographyRenderer.addHeading(title, 2, {
      y: 0.5
    });

    // Add chart using PptxGenJS chart functionality
    const dataChart = this.pres.addChart(pres.ChartType.bar, chartData, {
      x: 1,
      y: 1.5,
      w: 8,
      h: 4
    });

    return dataChart;
  }
}

/**
 * Export function for use in Python
 */
export function createEnhancedRenderer(presentation, designSystem) {
  return new EnhancedRenderer(presentation, designSystem);
}

export { DesignSystemRenderer, AdvancedEffectsRenderer, TypographyRenderer, EnhancedRenderer };
