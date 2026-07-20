import React, { useState, useEffect, useRef } from "react";
import { Streamlit, withStreamlitConnection } from "streamlit-component-lib";

/**
 * Canvas Editor Component for Archium Studio
 *
 * Features:
 * - Click to select elements
 * - Hover to highlight elements
 * - Visual element boundaries
 * - Color-coded element types
 */

interface Element {
  id: string;
  x: number;  // percentage (0-100)
  y: number;  // percentage (0-100)
  width: number;  // percentage (0-100)
  height: number;  // percentage (0-100)
  role: string;
  locked?: boolean;
  text_content?: string;
}

const ROLE_COLORS: Record<string, { border: string; background: string; label: string }> = {
  HERO_VISUAL: {
    border: "#175cd3",
    background: "rgba(23, 92, 211, 0.1)",
    label: "主视觉",
  },
  TITLE: {
    border: "#12b76a",
    background: "rgba(18, 183, 106, 0.1)",
    label: "标题",
  },
  BODY: {
    border: "#667085",
    background: "rgba(102, 112, 133, 0.1)",
    label: "正文",
  },
  CAPTION: {
    border: "#7a5af8",
    background: "rgba(122, 90, 248, 0.1)",
    label: "说明",
  },
  DECORATION: {
    border: "#f79009",
    background: "rgba(247, 144, 9, 0.1)",
    label: "装饰",
  },
};

const CanvasEditor: React.FC = () => {
  const [hoverElementId, setHoverElementId] = useState<string | null>(null);
  const [containerSize, setContainerSize] = useState({ width: 0, height: 0 });
  const containerRef = useRef<HTMLDivElement>(null);
  const imageRef = useRef<HTMLImageElement>(null);

  // Get props from Streamlit
  const args = (window as any).streamlitArgs;
  const imageUrl: string = args?.imageUrl || "";
  const elements: Element[] = args?.elements || [];
  const selectedId: string | null = args?.selectedId || null;
  const showLabels: boolean = args?.showLabels ?? true;
  const showAllBorders: boolean = args?.showAllBorders ?? true;

  // Measure container size
  useEffect(() => {
    const updateSize = () => {
      if (containerRef.current) {
        setContainerSize({
          width: containerRef.current.offsetWidth,
          height: containerRef.current.offsetHeight,
        });
      }
    };

    updateSize();
    window.addEventListener("resize", updateSize);
    return () => window.removeEventListener("resize", updateSize);
  }, []);

  // Notify Streamlit of component height
  useEffect(() => {
    if (imageRef.current) {
      const height = imageRef.current.offsetHeight + 40; // Add padding
      Streamlit.setFrameHeight(height);
    }
  }, [containerSize]);

  // Handle element click
  const handleElementClick = (elementId: string, event: React.MouseEvent) => {
    event.stopPropagation();
    Streamlit.setComponentValue(elementId);
  };

  // Handle canvas click (deselect)
  const handleCanvasClick = () => {
    Streamlit.setComponentValue(null);
  };

  // Find element at position
  const findElementAtPosition = (x: number, y: number): string | null => {
    // Check from top to bottom (reverse order for z-index)
    for (let i = elements.length - 1; i >= 0; i--) {
      const element = elements[i];
      if (
        x >= element.x &&
        x <= element.x + element.width &&
        y >= element.y &&
        y <= element.y + element.height
      ) {
        return element.id;
      }
    }
    return null;
  };

  // Handle mouse move for hover
  const handleMouseMove = (event: React.MouseEvent<HTMLDivElement>) => {
    if (!containerRef.current) return;

    const rect = containerRef.current.getBoundingClientRect();
    const x = ((event.clientX - rect.left) / rect.width) * 100;
    const y = ((event.clientY - rect.top) / rect.height) * 100;

    const elementId = findElementAtPosition(x, y);
    setHoverElementId(elementId);
  };

  // Render element boundary box
  const renderElementBox = (element: Element, isHovered: boolean, isSelected: boolean) => {
    const roleColor = ROLE_COLORS[element.role] || ROLE_COLORS.DECORATION;

    let border = roleColor.border;
    let background = roleColor.background;
    let borderWidth = "2px";
    let zIndex = 1;

    if (isSelected) {
      border = "#175cd3";
      background = "rgba(23, 92, 211, 0.15)";
      borderWidth = "3px";
      zIndex = 3;
    } else if (isHovered) {
      borderWidth = "2px";
      background = roleColor.background.replace("0.1", "0.2");
      zIndex = 2;
    }

    const style: React.CSSProperties = {
      position: "absolute",
      left: `${element.x}%`,
      top: `${element.y}%`,
      width: `${element.width}%`,
      height: `${element.height}%`,
      border: `${borderWidth} solid ${border}`,
      background: background,
      borderRadius: "4px",
      cursor: element.locked ? "not-allowed" : "pointer",
      transition: "all 0.15s ease",
      zIndex: zIndex,
      pointerEvents: "auto",
    };

    return (
      <div
        key={element.id}
        style={style}
        onClick={(e) => handleElementClick(element.id, e)}
        title={`${roleColor.label}: ${element.id}${element.locked ? " (锁定)" : ""}`}
      >
        {showLabels && (isSelected || isHovered) && (
          <div
            style={{
              position: "absolute",
              top: "-24px",
              left: "0",
              background: border,
              color: "white",
              padding: "2px 8px",
              borderRadius: "4px",
              fontSize: "12px",
              fontWeight: "600",
              whiteSpace: "nowrap",
              pointerEvents: "none",
            }}
          >
            {roleColor.label} · {element.id}
            {element.locked && " 🔒"}
          </div>
        )}
      </div>
    );
  };

  return (
    <div style={{ padding: "8px 0" }}>
      <div
        ref={containerRef}
        style={{
          position: "relative",
          width: "100%",
          aspectRatio: "16 / 9",
          overflow: "hidden",
          borderRadius: "8px",
          border: "1px solid #e4e4e7",
          cursor: "default",
        }}
        onMouseMove={handleMouseMove}
        onMouseLeave={() => setHoverElementId(null)}
        onClick={handleCanvasClick}
      >
        {/* Background image */}
        {imageUrl && (
          <img
            ref={imageRef}
            src={imageUrl}
            alt="Slide preview"
            style={{
              position: "absolute",
              top: 0,
              left: 0,
              width: "100%",
              height: "100%",
              objectFit: "contain",
              pointerEvents: "none",
            }}
          />
        )}

        {/* Element overlay layer */}
        <div
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            width: "100%",
            height: "100%",
            pointerEvents: "none",
          }}
        >
          {elements.map((element) => {
            const isSelected = element.id === selectedId;
            const isHovered = element.id === hoverElementId;
            const shouldShow = showAllBorders || isSelected || isHovered;

            if (!shouldShow) return null;

            return renderElementBox(element, isHovered, isSelected);
          })}
        </div>

        {/* Info overlay */}
        {hoverElementId && !selectedId && (
          <div
            style={{
              position: "absolute",
              bottom: "12px",
              right: "12px",
              background: "rgba(0, 0, 0, 0.75)",
              color: "white",
              padding: "8px 12px",
              borderRadius: "6px",
              fontSize: "13px",
              pointerEvents: "none",
            }}
          >
            点击选择元素
          </div>
        )}
      </div>

      {/* Legend */}
      {showAllBorders && (
        <div
          style={{
            marginTop: "12px",
            display: "flex",
            gap: "12px",
            flexWrap: "wrap",
            fontSize: "12px",
            color: "#667085",
          }}
        >
          {Object.entries(ROLE_COLORS).map(([role, config]) => (
            <div key={role} style={{ display: "flex", alignItems: "center", gap: "6px" }}>
              <div
                style={{
                  width: "16px",
                  height: "16px",
                  border: `2px solid ${config.border}`,
                  background: config.background,
                  borderRadius: "2px",
                }}
              />
              <span>{config.label}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default withStreamlitConnection(CanvasEditor);
