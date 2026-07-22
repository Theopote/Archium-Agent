import React, { useState, useEffect, useRef } from "react";
import { Streamlit, withStreamlitConnection } from "streamlit-component-lib";

/**
 * Canvas Editor Component for Archium Studio
 *
 * Features:
 * - Click to select elements
 * - Drag unlocked elements to reposition
 * - Hover to highlight elements
 */

interface Element {
  id: string;
  x: number;
  y: number;
  width: number;
  height: number;
  role: string;
  locked?: boolean;
  content_type?: string;
  text_content?: string;
}

type CanvasEvent =
  | { type: "select"; elementId: string | null }
  | { type: "move"; elementId: string; x: number; y: number }
  | {
      type: "resize";
      elementId: string;
      x: number;
      y: number;
      width: number;
      height: number;
      preserveAspectRatio?: boolean;
    }
  | { type: "editText"; elementId: string };

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

const DRAG_THRESHOLD_PX = 4;
const GEOMETRY_EPSILON = 0.05;

const CanvasEditor: React.FC = () => {
  const [hoverElementId, setHoverElementId] = useState<string | null>(null);
  const [dragElementId, setDragElementId] = useState<string | null>(null);
  const [dragPreview, setDragPreview] = useState<{ x: number; y: number } | null>(null);
  const [resizePreview, setResizePreview] = useState<{
    x: number;
    y: number;
    width: number;
    height: number;
  } | null>(null);
  const [containerSize, setContainerSize] = useState({ width: 0, height: 0 });
  const containerRef = useRef<HTMLDivElement>(null);
  const imageRef = useRef<HTMLImageElement>(null);
  const dragStateRef = useRef<{
    elementId: string;
    startClientX: number;
    startClientY: number;
    moved: boolean;
  } | null>(null);
  const resizeStateRef = useRef<{
    elementId: string;
    startX: number;
    startY: number;
    startWidth: number;
    startHeight: number;
    currentWidth: number;
    currentHeight: number;
    preserveAspectRatio: boolean;
  } | null>(null);

  const args = (window as any).streamlitArgs;
  const imageUrl: string = args?.imageUrl || "";
  const elements: Element[] = args?.elements || [];
  const selectedId: string | null = args?.selectedId || null;
  const showLabels: boolean = args?.showLabels ?? true;
  const showAllBorders: boolean = args?.showAllBorders ?? true;

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

  useEffect(() => {
    if (imageRef.current) {
      const height = imageRef.current.offsetHeight + 40;
      Streamlit.setFrameHeight(height);
    }
  }, [containerSize, dragElementId]);

  const emitEvent = (event: CanvasEvent) => {
    Streamlit.setComponentValue(event);
  };

  const percentFromClient = (clientX: number, clientY: number) => {
    if (!containerRef.current) {
      return { x: 0, y: 0 };
    }
    const rect = containerRef.current.getBoundingClientRect();
    return {
      x: ((clientX - rect.left) / rect.width) * 100,
      y: ((clientY - rect.top) / rect.height) * 100,
    };
  };

  const findElementAtPosition = (x: number, y: number): string | null => {
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

  const handleMouseMove = (event: React.MouseEvent<HTMLDivElement>) => {
    if (!containerRef.current) return;

    const { x, y } = percentFromClient(event.clientX, event.clientY);
    const activeResize = resizeStateRef.current;
    if (activeResize) {
      let nextWidth = Math.max(4, Math.min(100 - activeResize.startX, x - activeResize.startX));
      let nextHeight = Math.max(4, Math.min(100 - activeResize.startY, y - activeResize.startY));
      if (activeResize.preserveAspectRatio && activeResize.startHeight > 0) {
        const aspect = activeResize.startWidth / activeResize.startHeight;
        nextHeight = nextWidth / aspect;
        if (nextHeight > 100 - activeResize.startY) {
          nextHeight = 100 - activeResize.startY;
          nextWidth = nextHeight * aspect;
        }
      }
      activeResize.currentWidth = nextWidth;
      activeResize.currentHeight = nextHeight;
      setDragElementId(activeResize.elementId);
      setResizePreview({
        x: activeResize.startX,
        y: activeResize.startY,
        width: nextWidth,
        height: nextHeight,
      });
      return;
    }

    const activeDrag = dragStateRef.current;

    if (activeDrag) {
      const deltaX = event.clientX - activeDrag.startClientX;
      const deltaY = event.clientY - activeDrag.startClientY;
      if (Math.abs(deltaX) > DRAG_THRESHOLD_PX || Math.abs(deltaY) > DRAG_THRESHOLD_PX) {
        activeDrag.moved = true;
      }
      const element = elements.find((item) => item.id === activeDrag.elementId);
      if (element) {
        const previewX = Math.max(0, Math.min(100 - element.width, x - element.width / 2));
        const previewY = Math.max(0, Math.min(100 - element.height, y - element.height / 2));
        setDragElementId(activeDrag.elementId);
        setDragPreview({ x: previewX, y: previewY });
      }
      return;
    }

    const elementId = findElementAtPosition(x, y);
    setHoverElementId(elementId);
  };

  const finishDrag = (event: MouseEvent) => {
    const activeDrag = dragStateRef.current;
    dragStateRef.current = null;
    setDragElementId(null);
    setDragPreview(null);

    if (!activeDrag) return;

    if (activeDrag.moved) {
      const { x, y } = percentFromClient(event.clientX, event.clientY);
      const element = elements.find((item) => item.id === activeDrag.elementId);
      if (element) {
        const nextX = Math.max(0, Math.min(100 - element.width, x - element.width / 2));
        const nextY = Math.max(0, Math.min(100 - element.height, y - element.height / 2));
        if (
          Math.abs(nextX - element.x) < GEOMETRY_EPSILON &&
          Math.abs(nextY - element.y) < GEOMETRY_EPSILON
        ) {
          emitEvent({ type: "select", elementId: activeDrag.elementId });
          return;
        }
        emitEvent({
          type: "move",
          elementId: activeDrag.elementId,
          x: nextX,
          y: nextY,
        });
      }
      return;
    }

    emitEvent({ type: "select", elementId: activeDrag.elementId });
  };

  const finishResize = () => {
    const activeResize = resizeStateRef.current;
    resizeStateRef.current = null;
    setDragElementId(null);
    setResizePreview(null);
    if (!activeResize) return;
    const element = elements.find((item) => item.id === activeResize.elementId);
    if (
      element &&
      Math.abs(activeResize.currentWidth - element.width) < GEOMETRY_EPSILON &&
      Math.abs(activeResize.currentHeight - element.height) < GEOMETRY_EPSILON
    ) {
      return;
    }
    emitEvent({
      type: "resize",
      elementId: activeResize.elementId,
      x: activeResize.startX,
      y: activeResize.startY,
      width: activeResize.currentWidth,
      height: activeResize.currentHeight,
      preserveAspectRatio: activeResize.preserveAspectRatio,
    });
  };

  const handleResizeMouseDown = (
    element: Element,
    event: React.MouseEvent<HTMLDivElement>,
  ) => {
    event.stopPropagation();
    if (element.locked) {
      emitEvent({ type: "select", elementId: element.id });
      return;
    }
    resizeStateRef.current = {
      elementId: element.id,
      startX: element.x,
      startY: element.y,
      startWidth: element.width,
      startHeight: element.height,
      currentWidth: element.width,
      currentHeight: element.height,
      preserveAspectRatio: event.shiftKey,
    };
    setResizePreview({
      x: element.x,
      y: element.y,
      width: element.width,
      height: element.height,
    });
    const onPointerUp = (pointerEvent: PointerEvent) => {
      window.removeEventListener("pointerup", onPointerUp);
      finishResize();
    };
    window.addEventListener("pointerup", onPointerUp);
  };

  const handleElementMouseDown = (
    element: Element,
    event: React.MouseEvent<HTMLDivElement>,
  ) => {
    event.stopPropagation();
    if (element.locked) {
      emitEvent({ type: "select", elementId: element.id });
      return;
    }

    dragStateRef.current = {
      elementId: element.id,
      startClientX: event.clientX,
      startClientY: event.clientY,
      moved: false,
    };

    const onPointerUp = (pointerEvent: PointerEvent) => {
      window.removeEventListener("pointerup", onPointerUp);
      finishDrag(pointerEvent);
    };
    window.addEventListener("pointerup", onPointerUp);
  };

  const handleCanvasClick = () => {
    if (dragStateRef.current) return;
    emitEvent({ type: "select", elementId: null });
  };

  const handleElementDoubleClick = (
    element: Element,
    event: React.MouseEvent<HTMLDivElement>,
  ) => {
    event.stopPropagation();
    event.preventDefault();
    emitEvent({ type: "editText", elementId: element.id });
  };

  const renderElementBox = (element: Element, isHovered: boolean, isSelected: boolean) => {
    const roleColor = ROLE_COLORS[element.role] || ROLE_COLORS.DECORATION;
    const isDragging = dragElementId === element.id && dragPreview !== null;
    const isResizing = dragElementId === element.id && resizePreview !== null;
    const displayX = isResizing ? resizePreview.x : isDragging ? dragPreview.x : element.x;
    const displayY = isResizing ? resizePreview.y : isDragging ? dragPreview.y : element.y;
    const displayWidth = isResizing ? resizePreview.width : element.width;
    const displayHeight = isResizing ? resizePreview.height : element.height;

    let border = roleColor.border;
    let background = roleColor.background;
    let borderWidth = "2px";
    let zIndex = 1;

    if (isSelected || isDragging || isResizing) {
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
      left: `${displayX}%`,
      top: `${displayY}%`,
      width: `${displayWidth}%`,
      height: `${displayHeight}%`,
      border: `${borderWidth} solid ${border}`,
      background: background,
      borderRadius: "4px",
      cursor: element.locked ? "not-allowed" : isDragging || isResizing ? "grabbing" : "grab",
      transition: isDragging || isResizing ? "none" : "all 0.15s ease",
      zIndex: zIndex,
      pointerEvents: "auto",
    };

    const lockHint = element.locked
      ? element.content_type === "drawing"
        ? " (图纸锁定)"
        : " (锁定)"
      : "";

    return (
      <div
        key={element.id}
        style={style}
        onMouseDown={(event) => handleElementMouseDown(element, event)}
        onDoubleClick={(event) => handleElementDoubleClick(element, event)}
        title={`${roleColor.label}: ${element.id}${lockHint}`}
      >
        {showLabels && (isSelected || isHovered || isDragging || isResizing) && (
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
        {isSelected && !element.locked && (
          <div
            onMouseDown={(event) => handleResizeMouseDown(element, event)}
            style={{
              position: "absolute",
              right: "-6px",
              bottom: "-6px",
              width: "12px",
              height: "12px",
              borderRadius: "2px",
              background: "#175cd3",
              border: "2px solid white",
              cursor: "nwse-resize",
              zIndex: 4,
            }}
            title="拖拽调整尺寸（按住 Shift 保持比例）"
          />
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
          cursor: dragElementId ? "grabbing" : "default",
        }}
        onMouseMove={handleMouseMove}
        onMouseLeave={() => {
          if (!dragStateRef.current) {
            setHoverElementId(null);
          }
        }}
        onClick={handleCanvasClick}
      >
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
            const shouldShow =
              showAllBorders || isSelected || isHovered || dragElementId === element.id;
            if (!shouldShow) return null;
            return renderElementBox(element, isHovered, isSelected);
          })}
        </div>

        {hoverElementId && !selectedId && !dragElementId && (
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
            点击选择，拖拽移动
          </div>
        )}
      </div>

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
