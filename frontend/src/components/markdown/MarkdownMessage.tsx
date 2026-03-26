import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { CodeBlock } from "./CodeBlock";

function normalizeMarkdown(content: string) {
  return content
    .replace(/\r\n/g, "\n")
    .replace(/([。！？；：”」』》）])\s+(\d+\.\s+)/g, "$1\n\n$2")
    .replace(/([。！？；：”」』》）])\s+([*-]\s+)/g, "$1\n\n$2")
    .replace(/([。！？；：”」』》）])\s+(#{1,6}\s+)/g, "$1\n\n$2")
    .replace(/([。！？；：”」』》）])\s+((?:第[一二三四五六七八九十0-9]+阶段|总结|结论|补充说明)[:：])/g, "$1\n\n$2")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

export function MarkdownMessage({ content }: { content: string }) {
  const normalizedContent = normalizeMarkdown(content);

  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        h1: ({ children }) => (
          <h1 className="mb-4 text-[28px] font-semibold leading-tight tracking-[-0.03em]">
            {children}
          </h1>
        ),
        h2: ({ children }) => (
          <h2 className="mb-3 text-[24px] font-semibold leading-tight tracking-[-0.03em]">
            {children}
          </h2>
        ),
        h3: ({ children }) => (
          <h3 className="mb-3 text-[20px] font-semibold leading-tight tracking-[-0.02em]">
            {children}
          </h3>
        ),
        p: ({ children }) => <p className="mb-4 last:mb-0">{children}</p>,
        ul: ({ children }) => <ul className="mb-4 list-disc space-y-2 pl-6 last:mb-0">{children}</ul>,
        ol: ({ children }) => <ol className="mb-4 list-decimal space-y-2 pl-6 last:mb-0">{children}</ol>,
        li: ({ children }) => <li>{children}</li>,
        hr: () => <hr className="my-6 border-app-border" />,
        blockquote: ({ children }) => (
          <blockquote className="mb-4 border-l-2 border-app-border pl-4 text-app-muted">
            {children}
          </blockquote>
        ),
        table: ({ children }) => (
          <div className="mb-4 overflow-x-auto rounded-[16px] border border-app-border last:mb-0">
            <table className="min-w-full border-collapse bg-app-panel-strong text-[14px] leading-7">
              {children}
            </table>
          </div>
        ),
        thead: ({ children }) => <thead className="bg-[#f4ecdf]">{children}</thead>,
        tbody: ({ children }) => <tbody>{children}</tbody>,
        tr: ({ children }) => <tr className="border-b border-app-border last:border-b-0">{children}</tr>,
        th: ({ children }) => (
          <th className="px-4 py-3 text-left text-[13px] font-semibold tracking-[0.02em] text-app-text">
            {children}
          </th>
        ),
        td: ({ children }) => <td className="px-4 py-3 align-top text-app-text">{children}</td>,
        code: ({ className, children }) =>
          className ? (
            <CodeBlock className={className}>{children}</CodeBlock>
          ) : (
            <code className="rounded-md bg-app-panel-soft px-1.5 py-0.5 text-[0.92em]">
              {children}
            </code>
          ),
        pre: ({ children }) => <>{children}</>,
        a: ({ href, children }) => (
          <a
            className="text-app-accent-strong underline underline-offset-4"
            href={href}
            rel="noreferrer"
            target="_blank"
          >
            {children}
          </a>
        ),
        strong: ({ children }) => <strong className="font-semibold text-app-text">{children}</strong>,
      }}
    >
      {normalizedContent}
    </ReactMarkdown>
  );
}
