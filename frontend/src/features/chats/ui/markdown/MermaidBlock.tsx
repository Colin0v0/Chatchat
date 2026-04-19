import { Minus, Plus, RotateCcw } from "lucide-react";
import { memo, useEffect, useId, useRef, useState } from "react";

const MERMAID_THEME = "neutral";
const MIN_ZOOM = 0.6;
const MAX_ZOOM = 2;
const ZOOM_STEP = 0.2;

type MermaidModule = typeof import("mermaid")["default"];
type MermaidRenderResult = {
  svg: string;
  bindFunctions?: (element: Element) => void;
};

let mermaidPromise: Promise<MermaidModule> | null = null;
let mermaidInitialized = false;
const mermaidRenderCache = new Map<string, MermaidRenderResult>();

async function getMermaid() {
  if (!mermaidPromise) {
    mermaidPromise = import("mermaid").then(({ default: mermaid }) => {
      if (!mermaidInitialized) {
        mermaid.initialize({
          startOnLoad: false,
          theme: MERMAID_THEME,
          securityLevel: "loose",
        });
        mermaidInitialized = true;
      }

      return mermaid;
    });
  }

  return mermaidPromise;
}

function clampZoom(value: number) {
  return Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, Number(value.toFixed(2))));
}

function MermaidBlockComponent({ chart }: { chart: string }) {
  const [error, setError] = useState<string | null>(null);
  const [isRendering, setIsRendering] = useState(() => !mermaidRenderCache.has(chart));
  const [zoom, setZoom] = useState(1);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const viewportRef = useRef<HTMLDivElement | null>(null);
  const dragStateRef = useRef<{
    active: boolean;
    pointerId: number | null;
    startX: number;
    startY: number;
    scrollLeft: number;
    scrollTop: number;
  }>({
    active: false,
    pointerId: null,
    startX: 0,
    startY: 0,
    scrollLeft: 0,
    scrollTop: 0,
  });
  const id = useId().replace(/:/g, "-");

  useEffect(() => {
    setZoom(1);
  }, [chart]);

  useEffect(() => {
    let cancelled = false;

    async function renderChart() {
      const cached = mermaidRenderCache.get(chart);
      if (cached) {
        if (!containerRef.current) {
          return;
        }

        containerRef.current.innerHTML = cached.svg;
        cached.bindFunctions?.(containerRef.current);
        setError(null);
        setIsRendering(false);
        return;
      }

      setIsRendering(true);

      try {
        const mermaid = await getMermaid();
        const rendered = await mermaid.render(`mermaid-${id}`, chart);
        if (cancelled || !containerRef.current) {
          return;
        }

        mermaidRenderCache.set(chart, rendered);
        containerRef.current.innerHTML = rendered.svg;
        rendered.bindFunctions?.(containerRef.current);
        setError(null);
      } catch (renderError: unknown) {
        if (cancelled) {
          return;
        }

        setError(renderError instanceof Error ? renderError.message : "Failed to render mermaid diagram.");
      } finally {
        if (!cancelled) {
          setIsRendering(false);
        }
      }
    }

    void renderChart();

    return () => {
      cancelled = true;
    };
  }, [chart, id]);

  function handlePointerDown(event: React.PointerEvent<HTMLDivElement>) {
    const viewport = viewportRef.current;
    if (!viewport) {
      return;
    }

    dragStateRef.current = {
      active: true,
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      scrollLeft: viewport.scrollLeft,
      scrollTop: viewport.scrollTop,
    };

    viewport.setPointerCapture(event.pointerId);
  }

  function handlePointerMove(event: React.PointerEvent<HTMLDivElement>) {
    const viewport = viewportRef.current;
    const dragState = dragStateRef.current;
    if (!viewport || !dragState.active) {
      return;
    }

    viewport.scrollLeft = dragState.scrollLeft - (event.clientX - dragState.startX);
    viewport.scrollTop = dragState.scrollTop - (event.clientY - dragState.startY);
  }

  function handlePointerUp(event: React.PointerEvent<HTMLDivElement>) {
    const viewport = viewportRef.current;
    if (viewport && dragStateRef.current.pointerId !== null) {
      viewport.releasePointerCapture(event.pointerId);
    }

    dragStateRef.current.active = false;
    dragStateRef.current.pointerId = null;
  }

  if (error) {
    return (
      <div className="mb-4 rounded-[20px] border border-[#e0c9c1] bg-[#fbf1ee] px-4 py-3 text-[14px] leading-7 text-[#8a3329]">
        Mermaid render failed: {error}
      </div>
    );
  }

  return (
    <div className="mb-4 overflow-hidden rounded-[20px] border border-app-border bg-[#f6f1e8] last:mb-0">
      <div className="flex items-center justify-between border-b border-app-border bg-[#efe6d8] px-4 py-2.5">
        <div className="text-[12px] font-semibold uppercase tracking-[0.12em] text-app-muted">Mermaid</div>
        <div className="flex items-center gap-1.5 text-app-muted">
          <button
            aria-label="Zoom out"
            className="flex h-8 w-8 items-center justify-center rounded-lg transition hover:bg-white/60 hover:text-app-text"
            onClick={() => setZoom((current) => clampZoom(current - ZOOM_STEP))}
            type="button"
          >
            <Minus className="size-3.5" />
          </button>
          <button
            aria-label="Reset zoom"
            className="min-w-[56px] rounded-lg px-2 py-1 text-[12px] font-medium transition hover:bg-white/60 hover:text-app-text"
            onClick={() => setZoom(1)}
            type="button"
          >
            {Math.round(zoom * 100)}%
          </button>
          <button
            aria-label="Zoom in"
            className="flex h-8 w-8 items-center justify-center rounded-lg transition hover:bg-white/60 hover:text-app-text"
            onClick={() => setZoom((current) => clampZoom(current + ZOOM_STEP))}
            type="button"
          >
            <Plus className="size-3.5" />
          </button>
          <button
            aria-label="Reset position"
            className="flex h-8 w-8 items-center justify-center rounded-lg transition hover:bg-white/60 hover:text-app-text"
            onClick={() => {
              setZoom(1);
              viewportRef.current?.scrollTo({ left: 0, top: 0, behavior: "smooth" });
            }}
            type="button"
          >
            <RotateCcw className="size-3.5" />
          </button>
        </div>
      </div>

      <div
        className={`app-scrollbar relative overflow-auto px-4 py-4 ${dragStateRef.current.active ? "cursor-grabbing" : "cursor-grab"}`}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerCancel={handlePointerUp}
        ref={viewportRef}
      >
        {isRendering ? <div className="mb-3 text-[14px] text-app-muted">Rendering diagram...</div> : null}
        <div className="min-w-fit origin-top-left" style={{ transform: `scale(${zoom})` }}>
          <div className="min-w-fit select-none touch-none" ref={containerRef} />
        </div>
      </div>
    </div>
  );
}

export const MermaidBlock = memo(MermaidBlockComponent);