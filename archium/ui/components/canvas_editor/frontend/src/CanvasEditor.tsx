import React, { useState, useEffect, useRef } from "react";
import { Streamlit, withStreamlitConnection } from "streamlit-component-lib";

/**
 * Canvas Editor — Studio Essential Editing V1
 *
 * pointermove → local preview only (no Streamlit traffic)
 * pointerup   → one Command event (move / moveMany / resize / commitText / …)
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

interface CommentAnchor {
  id: string;
  nodeId?: string;
  elementId?: string;
  status: string;
  kind: "node" | "region";
  x: number;
  y: number;
  width?: number;
  height?: number;
  focused?: boolean;
}

interface AssetOption {
  id: string;
  label: string;
  storageUri?: string;
}

type CanvasEvent =
  | { type: "select"; elementId: string | null; elementIds?: string[] }
  | { type: "move"; elementId: string; x: number; y: number }
  | {
      type: "moveMany";
      moves: Array<{ elementId: string; x: number; y: number }>;
    }
  | {
      type: "resize";
      elementId: string;
      x: number;
      y: number;
      width: number;
      height: number;
      preserveAspectRatio?: boolean;
    }
  | { type: "editText"; elementId: string }
  | { type: "commitText"; elementId: string; text: string }
  | { type: "commitReplaceAsset"; elementId: string; assetId: string }
  | { type: "requestReplaceAsset"; elementId: string };

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

const isTextContent = (contentType?: string) =>
  (contentType || "").toLowerCase() === "text";
const isImageContent = (contentType?: string) =>
  (contentType || "").toLowerCase() === "image";

const CanvasEditor: React.FC = () => {
  const [hoverElementId, setHoverElementId] = useState<string | null>(null);
  const [localSelectedIds, setLocalSelectedIds] = useState<string[]>([]);
  const [dragElementId, setDragElementId] = useState<string | null>(null);
  const [dragPreviewById, setDragPreviewById] = useState<Record<string, { x: number; y: number }>>(
    {},
  );
  const [resizePreview, setResizePreview] = useState<{
    x: number;
    y: number;
    width: number;
    height: number;
  } | null>(null);
  const [marquee, setMarquee] = useState<{
    x0: number;
    y0: number;
    x1: number;
    y1: number;
  } | null>(null);
  const [inlineEdit, setInlineEdit] = useState<{
    elementId: string;
    text: string;
    x: number;
    y: number;
    width: number;
    height: number;
  } | null>(null);
  const [assetPicker, setAssetPicker] = useState<{
    elementId: string;
    x: number;
    y: number;
    width: number;
    height: number;
  } | null>(null);
  const [containerSize, setContainerSize] = useState({ width: 0, height: 0 });
  const containerRef = useRef<HTMLDivElement>(null);
  const imageRef = useRef<HTMLImageElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const dragStateRef = useRef<{
    elementIds: string[];
    anchorId: string;
    startClientX: number;
    startClientY: number;
    startPositions: Record<string, { x: number; y: number }>;
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
  const marqueeStateRef = useRef<{
    startX: number;
    startY: number;
    additive: boolean;
  } | null>(null);

  const args = (window as any).streamlitArgs;
  const imageUrl: string = args?.imageUrl || "";
  const elements: Element[] = args?.elements || [];
  const selectedId: string | null = args?.selectedId || null;
  const selectedIdsProp: string[] = Array.isArray(args?.selectedIds)
    ? args.selectedIds.map(String)
    : selectedId
      ? [selectedId]
      : [];
  const showLabels: boolean = args?.showLabels ?? true;
  const showAllBorders: boolean = args?.showAllBorders ?? true;
  const assets: AssetOption[] = Array.isArray(args?.assets) ? args.assets : [];
  const commentAnchors: CommentAnchor[] = Array.isArray(args?.commentAnchors)
    ? args.commentAnchors
    : [];

  useEffect(() => {
    setLocalSelectedIds(selectedIdsProp);
  }, [selectedIdsProp.join("|")]);

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
  }, [containerSize, dragElementId, inlineEdit, assetPicker, commentAnchors.length]);

  useEffect(() => {
    if (inlineEdit && textareaRef.current) {
      textareaRef.current.focus();
      textareaRef.current.select();
    }
  }, [inlineEdit?.elementId]);

  const emitEvent = (event: CanvasEvent) => {
    Streamlit.setComponentValue(event);
  };

  const selectedIds = localSelectedIds.length ? localSelectedIds : selectedIdsProp;

  const emitSelection = (ids: string[]) => {
    setLocalSelectedIds(ids);
    emitEvent({
      type: "select",
      elementId: ids[0] ?? null,
      elementIds: ids,
    });
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

  const elementsInRect = (x0: number, y0: number, x1: number, y1: number): string[] => {
    const left = Math.min(x0, x1);
    const right = Math.max(x0, x1);
    const top = Math.min(y0, y1);
    const bottom = Math.max(y0, y1);
    return elements
      .filter((element) => {
        const ex1 = element.x + element.width;
        const ey1 = element.y + element.height;
        return element.x < right && ex1 > left && element.y < bottom && ey1 > top;
      })
      .map((element) => element.id);
  };

  const handleMouseMove = (event: React.MouseEvent<HTMLDivElement>) => {
    if (!containerRef.current) return;

    const { x, y } = percentFromClient(event.clientX, event.clientY);
    const activeMarquee = marqueeStateRef.current;
    if (activeMarquee) {
      setMarquee({
        x0: activeMarquee.startX,
        y0: activeMarquee.startY,
        x1: x,
        y1: y,
      });
      return;
    }

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
      const rect = containerRef.current.getBoundingClientRect();
      const dxPercent = (deltaX / rect.width) * 100;
      const dyPercent = (deltaY / rect.height) * 100;
      const nextPreview: Record<string, { x: number; y: number }> = {};
      for (const id of activeDrag.elementIds) {
        const element = elements.find((item) => item.id === id);
        const start = activeDrag.startPositions[id];
        if (!element || !start) continue;
        nextPreview[id] = {
          x: Math.max(0, Math.min(100 - element.width, start.x + dxPercent)),
          y: Math.max(0, Math.min(100 - element.height, start.y + dyPercent)),
        };
      }
      setDragElementId(activeDrag.anchorId);
      setDragPreviewById(nextPreview);
      return;
    }

    const elementId = findElementAtPosition(x, y);
    setHoverElementId(elementId);
  };

  const finishDrag = (_event: MouseEvent) => {
    const activeDrag = dragStateRef.current;
    dragStateRef.current = null;
    const preview = { ...dragPreviewById };
    setDragElementId(null);
    setDragPreviewById({});

    if (!activeDrag) return;

    if (activeDrag.moved) {
      const moves = activeDrag.elementIds
        .map((id) => {
          const element = elements.find((item) => item.id === id);
          const next = preview[id];
          if (!element || !next) return null;
          if (
            Math.abs(next.x - element.x) < GEOMETRY_EPSILON &&
            Math.abs(next.y - element.y) < GEOMETRY_EPSILON
          ) {
            return null;
          }
          return { elementId: id, x: next.x, y: next.y };
        })
        .filter(Boolean) as Array<{ elementId: string; x: number; y: number }>;

      if (moves.length === 0) {
        emitSelection(activeDrag.elementIds);
        return;
      }
      if (moves.length === 1) {
        emitEvent({
          type: "move",
          elementId: moves[0].elementId,
          x: moves[0].x,
          y: moves[0].y,
        });
        return;
      }
      emitEvent({ type: "moveMany", moves });
      return;
    }

    emitSelection(activeDrag.elementIds);
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

  const finishMarquee = () => {
    const active = marqueeStateRef.current;
    const box = marquee;
    marqueeStateRef.current = null;
    setMarquee(null);
    if (!active || !box) return;
    const hit = elementsInRect(box.x0, box.y0, box.x1, box.y1);
    if (active.additive) {
      const merged = Array.from(new Set([...selectedIds, ...hit]));
      emitSelection(merged);
    } else {
      emitSelection(hit);
    }
  };

  const handleResizeMouseDown = (
    element: Element,
    event: React.MouseEvent<HTMLDivElement>,
  ) => {
    event.stopPropagation();
    if (element.locked) {
      emitSelection([element.id]);
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
    const onPointerUp = () => {
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
    if (inlineEdit || assetPicker) return;

    let nextIds = selectedIds.includes(element.id) ? [...selectedIds] : [element.id];
    if (event.shiftKey) {
      if (selectedIds.includes(element.id)) {
        nextIds = selectedIds.filter((id) => id !== element.id);
      } else {
        nextIds = [...selectedIds, element.id];
      }
      setLocalSelectedIds(nextIds);
    } else if (!selectedIds.includes(element.id)) {
      setLocalSelectedIds([element.id]);
      nextIds = [element.id];
    }

    if (element.locked) {
      emitSelection(nextIds.length ? nextIds : [element.id]);
      return;
    }

    const dragIds = nextIds.filter((id) => {
      const item = elements.find((el) => el.id === id);
      return item && !item.locked;
    });
    if (dragIds.length === 0) {
      emitSelection(nextIds);
      return;
    }

    const startPositions: Record<string, { x: number; y: number }> = {};
    for (const id of dragIds) {
      const item = elements.find((el) => el.id === id);
      if (item) startPositions[id] = { x: item.x, y: item.y };
    }

    dragStateRef.current = {
      elementIds: dragIds,
      anchorId: element.id,
      startClientX: event.clientX,
      startClientY: event.clientY,
      startPositions,
      moved: false,
    };

    const onPointerUp = (pointerEvent: PointerEvent) => {
      window.removeEventListener("pointerup", onPointerUp);
      finishDrag(pointerEvent);
    };
    window.addEventListener("pointerup", onPointerUp);
  };

  const handleCanvasMouseDown = (event: React.MouseEvent<HTMLDivElement>) => {
    if (event.target !== event.currentTarget) return;
    if (inlineEdit || assetPicker) return;
    const { x, y } = percentFromClient(event.clientX, event.clientY);
    if (findElementAtPosition(x, y)) return;
    marqueeStateRef.current = {
      startX: x,
      startY: y,
      additive: event.shiftKey,
    };
    setMarquee({ x0: x, y0: y, x1: x, y1: y });
    const onPointerUp = () => {
      window.removeEventListener("pointerup", onPointerUp);
      finishMarquee();
    };
    window.addEventListener("pointerup", onPointerUp);
  };

  const commitInlineText = () => {
    if (!inlineEdit) return;
    const payload = { ...inlineEdit };
    setInlineEdit(null);
    const original = elements.find((item) => item.id === payload.elementId);
    if (original && original.text_content === payload.text) {
      emitSelection([payload.elementId]);
      return;
    }
    emitEvent({
      type: "commitText",
      elementId: payload.elementId,
      text: payload.text,
    });
  };

  const handleElementDoubleClick = (
    element: Element,
    event: React.MouseEvent<HTMLDivElement>,
  ) => {
    event.stopPropagation();
    event.preventDefault();
    if (element.locked) {
      emitSelection([element.id]);
      return;
    }
    if (isTextContent(element.content_type)) {
      setAssetPicker(null);
      setInlineEdit({
        elementId: element.id,
        text: element.text_content || "",
        x: element.x,
        y: element.y,
        width: element.width,
        height: element.height,
      });
      setLocalSelectedIds([element.id]);
      return;
    }
    if (isImageContent(element.content_type)) {
      setInlineEdit(null);
      setLocalSelectedIds([element.id]);
      if (assets.length > 0) {
        setAssetPicker({
          elementId: element.id,
          x: element.x,
          y: element.y,
          width: Math.max(element.width, 18),
          height: Math.max(element.height, 12),
        });
      } else {
        emitEvent({ type: "requestReplaceAsset", elementId: element.id });
      }
      return;
    }
    emitEvent({ type: "editText", elementId: element.id });
  };

  const renderElementBox = (element: Element, isHovered: boolean, isSelected: boolean) => {
    const roleColor = ROLE_COLORS[element.role] || ROLE_COLORS.DECORATION;
    const preview = dragPreviewById[element.id];
    const isDragging = preview !== undefined;
    const isResizing = dragElementId === element.id && resizePreview !== null;
    const displayX = isResizing ? resizePreview.x : isDragging ? preview.x : element.x;
    const displayY = isResizing ? resizePreview.y : isDragging ? preview.y : element.y;
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
        {isSelected && selectedIds.length === 1 && !element.locked && (
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

  const marqueeStyle: React.CSSProperties | null = marquee
    ? {
        position: "absolute",
        left: `${Math.min(marquee.x0, marquee.x1)}%`,
        top: `${Math.min(marquee.y0, marquee.y1)}%`,
        width: `${Math.abs(marquee.x1 - marquee.x0)}%`,
        height: `${Math.abs(marquee.y1 - marquee.y0)}%`,
        border: "1px dashed #175cd3",
        background: "rgba(23, 92, 211, 0.08)",
        pointerEvents: "none",
        zIndex: 5,
      }
    : null;

  const commentStatusColor = (status: string, focused?: boolean): string => {
    if (focused) return "#d92d20";
    if (status === "needs_rebase") return "#dc6803";
    if (status === "proposed") return "#175cd3";
    return "#f79009";
  };

  const renderCommentAnchors = () => {
    if (!commentAnchors.length) return null;
    return (
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          width: "100%",
          height: "100%",
          pointerEvents: "none",
          zIndex: 4,
        }}
      >
        {commentAnchors.map((anchor) => {
          const color = commentStatusColor(anchor.status, anchor.focused);
          if (anchor.kind === "region") {
            return (
              <div
                key={anchor.id}
                title={`评论选区 · ${anchor.status}`}
                style={{
                  position: "absolute",
                  left: `${anchor.x}%`,
                  top: `${anchor.y}%`,
                  width: `${Math.max(anchor.width || 0, 0.5)}%`,
                  height: `${Math.max(anchor.height || 0, 0.5)}%`,
                  border: `2px dashed ${color}`,
                  background: anchor.focused
                    ? "rgba(217, 45, 32, 0.08)"
                    : "rgba(247, 144, 9, 0.06)",
                  borderRadius: "4px",
                  boxSizing: "border-box",
                }}
              />
            );
          }
          return (
            <div
              key={anchor.id}
              title={`评论 · ${anchor.status} · ${anchor.nodeId || ""}`}
              style={{
                position: "absolute",
                left: `${anchor.x}%`,
                top: `${anchor.y}%`,
                transform: "translate(-50%, -50%)",
                width: anchor.focused ? 16 : 12,
                height: anchor.focused ? 16 : 12,
                borderRadius: "50%",
                background: color,
                border: "2px solid white",
                boxShadow: "0 1px 4px rgba(0,0,0,0.25)",
              }}
            />
          );
        })}
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
          cursor: dragElementId || marquee ? "crosshair" : "default",
        }}
        onMouseMove={handleMouseMove}
        onMouseDown={handleCanvasMouseDown}
        onMouseLeave={() => {
          if (!dragStateRef.current && !marqueeStateRef.current) {
            setHoverElementId(null);
          }
        }}
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
            const isSelected = selectedIds.includes(element.id);
            const isHovered = element.id === hoverElementId;
            const shouldShow =
              showAllBorders ||
              isSelected ||
              isHovered ||
              dragPreviewById[element.id] !== undefined;
            if (!shouldShow) return null;
            return renderElementBox(element, isHovered, isSelected);
          })}
        </div>

        {marqueeStyle && <div style={marqueeStyle} />}

        {renderCommentAnchors()}

        {inlineEdit && (
          <textarea
            ref={textareaRef}
            value={inlineEdit.text}
            onChange={(event) =>
              setInlineEdit({ ...inlineEdit, text: event.target.value })
            }
            onBlur={commitInlineText}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                commitInlineText();
              }
              if (event.key === "Escape") {
                event.preventDefault();
                setInlineEdit(null);
              }
            }}
            style={{
              position: "absolute",
              left: `${inlineEdit.x}%`,
              top: `${inlineEdit.y}%`,
              width: `${inlineEdit.width}%`,
              height: `${Math.max(inlineEdit.height, 8)}%`,
              zIndex: 6,
              resize: "none",
              fontSize: "14px",
              padding: "6px",
              border: "2px solid #175cd3",
              borderRadius: "4px",
              boxSizing: "border-box",
            }}
          />
        )}

        {assetPicker && (
          <div
            style={{
              position: "absolute",
              left: `${assetPicker.x}%`,
              top: `${assetPicker.y}%`,
              width: `${Math.min(assetPicker.width, 40)}%`,
              zIndex: 6,
              background: "white",
              border: "2px solid #175cd3",
              borderRadius: "6px",
              padding: "8px",
              boxShadow: "0 4px 16px rgba(0,0,0,0.12)",
            }}
            onMouseDown={(event) => event.stopPropagation()}
          >
            <div style={{ fontSize: "12px", fontWeight: 600, marginBottom: "6px" }}>
              更换素材
            </div>
            <select
              defaultValue=""
              style={{ width: "100%", fontSize: "12px" }}
              onChange={(event) => {
                const assetId = event.target.value;
                if (!assetId) return;
                const elementId = assetPicker.elementId;
                setAssetPicker(null);
                emitEvent({
                  type: "commitReplaceAsset",
                  elementId,
                  assetId,
                });
              }}
            >
              <option value="" disabled>
                选择图片…
              </option>
              {assets.map((asset) => (
                <option key={asset.id} value={asset.id}>
                  {asset.label}
                </option>
              ))}
            </select>
            <button
              type="button"
              style={{ marginTop: "6px", fontSize: "12px", width: "100%" }}
              onClick={() => setAssetPicker(null)}
            >
              取消
            </button>
          </div>
        )}

        {hoverElementId && selectedIds.length === 0 && !dragElementId && !marquee && (
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
            点击选择 · Shift 多选 · 框选 · 双击改字/换图
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
