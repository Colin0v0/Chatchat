import { Check, Copy } from "lucide-react";
import { useState, type ReactNode } from "react";

import { MermaidBlock } from "./MermaidBlock";

export function CodeBlock({
  className,
  children,
}: {
  className?: string;
  children: ReactNode;
}) {
  const [copied, setCopied] = useState(false);
  const language = className?.replace(/^language-/, "") || "text";
  const code = String(children).replace(/\n$/, "");

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1200);
    } catch {
      setCopied(false);
    }
  }

  if (language === "mermaid") {
    return <MermaidBlock chart={code} />;
  }

  return (
    <div className="mb-4 overflow-hidden rounded-[20px] border border-app-border bg-[#f6f1e8] last:mb-0">
      <div className="flex items-center justify-between border-b border-app-border bg-[#efe6d8] px-4 py-2.5">
        <span className="text-[12px] font-semibold uppercase tracking-[0.12em] text-app-muted">
          {language}
        </span>
        <button
          aria-label="Copy code"
          className="flex h-8 w-8 items-center justify-center rounded-lg text-app-muted transition hover:bg-white/60 hover:text-app-text"
          onClick={() => void handleCopy()}
          type="button"
        >
          {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
        </button>
      </div>
      <pre className="overflow-x-auto px-4 py-3 text-[14px] leading-7 text-app-text">
        <code>{code}</code>
      </pre>
    </div>
  );
}
