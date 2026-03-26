import mermaid from "mermaid";
import { useEffect, useId, useRef, useState } from "react";

const MERMAID_THEME = "neutral";
let mermaidInitialized = false;

function ensureMermaidInitialized() {
  if (mermaidInitialized) {
    return;
  }

  mermaid.initialize({
    startOnLoad: false,
    theme: MERMAID_THEME,
    securityLevel: "loose",
  });
  mermaidInitialized = true;
}

export function MermaidBlock({ chart }: { chart: string }) {
  const [error, setError] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const id = useId().replace(/:/g, "-");

  useEffect(() => {
    let cancelled = false;
    ensureMermaidInitialized();

    void mermaid
      .render(`mermaid-${id}`, chart)
      .then(({ svg, bindFunctions }) => {
        if (cancelled || !containerRef.current) {
          return;
        }
        containerRef.current.innerHTML = svg;
        bindFunctions?.(containerRef.current);
        setError(null);
      })
      .catch((renderError: unknown) => {
        if (cancelled) {
          return;
        }
        setError(renderError instanceof Error ? renderError.message : "Failed to render mermaid diagram.");
      });

    return () => {
      cancelled = true;
    };
  }, [chart, id]);

  if (error) {
    return (
      <div className="mb-4 rounded-[20px] border border-[#e0c9c1] bg-[#fbf1ee] px-4 py-3 text-[14px] leading-7 text-[#8a3329]">
        Mermaid render failed: {error}
      </div>
    );
  }

  return (
    <div className="mb-4 overflow-x-auto rounded-[20px] border border-app-border bg-[#f6f1e8] px-4 py-4 last:mb-0">
      <div className="min-w-fit" ref={containerRef} />
    </div>
  );
}
