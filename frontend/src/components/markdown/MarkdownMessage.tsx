import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import { memo, useMemo, type ReactNode } from "react";

import { CodeBlock } from "./CodeBlock";

const sentenceBreakPattern = /([\u3002\uff01\uff1f\uff1b\uff1a\u201d\u300d\u300f\u300b\uff09])\s+/g;
const stageHeadingPattern = /((?:\u7b2c[\u4e00\u4e8c\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d\u53410-9]+\u9636\u6bb5|\u603b\u7ed3|\u7ed3\u8bba|\u8865\u5145\u8bf4\u660e)[:\uff1a])/g;

function normalizeMathDelimiters(content: string) {
  const withExplicitDelimiters = content
    .replace(/\\\[([\s\S]*?)\\\]/g, (_, expression: string) => `\n$$\n${expression.trim()}\n$$\n`)
    .replace(/\\\(([\s\S]*?)\\\)/g, (_, expression: string) => `$${expression.trim()}$`);

  // Some models emit raw TeX blocks without any delimiters (no $...$ / $$...$$ / \[...\]).
  // Wrap those paragraphs as display math so KaTeX can render them.
  const segments = withExplicitDelimiters.split(/```/g);
  for (let index = 0; index < segments.length; index += 1) {
    // Odd indices are inside fenced code blocks.
    if (index % 2 === 1) {
      continue;
    }

    const paragraphs = segments[index].split(/\n{2,}/g);
    segments[index] = paragraphs
      .map((paragraph) => {
        const trimmed = paragraph.trim();
        if (!trimmed) {
          return paragraph;
        }
        if (/[`$]/.test(trimmed) || /\\\[|\\\(|\\\]/.test(trimmed)) {
          return paragraph;
        }

        if (
          trimmed.startsWith("\\") &&
          /\\[A-Za-z]+/.test(trimmed) &&
          (/[{}_^]/.test(trimmed) || /\\\\/.test(trimmed) || /\\begin\{/.test(trimmed))
        ) {
          return `$$\n${trimmed}\n$$`;
        }

        return paragraph;
      })
      .join("\n\n");
  }

  return segments.join("```");
}

function normalizeMarkdown(content: string) {
  return normalizeMathDelimiters(content)
    .replace(/\r\n/g, "\n")
    .replace(sentenceBreakPattern, (match, punctuation, offset, source) => {
      const remainder = source.slice(offset + match.length);
      if (/^(\d+\.\s+|[*-]\s+|#{1,6}\s+)/.test(remainder) || stageHeadingPattern.test(remainder)) {
        stageHeadingPattern.lastIndex = 0;
        return `${punctuation}\n\n`;
      }
      stageHeadingPattern.lastIndex = 0;
      return match;
    })
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

const markdownComponents = {
  h1: ({ children }: { children?: ReactNode }) => (
    <h1 className="mb-4 text-[28px] font-semibold leading-tight tracking-[-0.03em]">{children}</h1>
  ),
  h2: ({ children }: { children?: ReactNode }) => (
    <h2 className="mb-3 text-[24px] font-semibold leading-tight tracking-[-0.03em]">{children}</h2>
  ),
  h3: ({ children }: { children?: ReactNode }) => (
    <h3 className="mb-3 text-[20px] font-semibold leading-tight tracking-[-0.02em]">{children}</h3>
  ),
  p: ({ children }: { children?: ReactNode }) => <p className="mb-4 last:mb-0">{children}</p>,
  ul: ({ children }: { children?: ReactNode }) => <ul className="mb-4 list-disc space-y-2 pl-6 last:mb-0">{children}</ul>,
  ol: ({ children }: { children?: ReactNode }) => <ol className="mb-4 list-decimal space-y-2 pl-6 last:mb-0">{children}</ol>,
  li: ({ children }: { children?: ReactNode }) => <li>{children}</li>,
  hr: () => <hr className="my-6 border-app-border" />,
  blockquote: ({ children }: { children?: ReactNode }) => (
    <blockquote className="mb-4 border-l-2 border-app-border pl-4 text-app-muted">{children}</blockquote>
  ),
  table: ({ children }: { children?: ReactNode }) => (
    <div className="mb-4 overflow-x-auto rounded-[16px] border border-app-border last:mb-0">
      <table className="min-w-full border-collapse bg-app-panel-strong text-[14px] leading-7">{children}</table>
    </div>
  ),
  thead: ({ children }: { children?: ReactNode }) => <thead className="bg-[#f4ecdf]">{children}</thead>,
  tbody: ({ children }: { children?: ReactNode }) => <tbody>{children}</tbody>,
  tr: ({ children }: { children?: ReactNode }) => <tr className="border-b border-app-border last:border-b-0">{children}</tr>,
  th: ({ children }: { children?: ReactNode }) => (
    <th className="px-4 py-3 text-left text-[13px] font-semibold tracking-[0.02em] text-app-text">{children}</th>
  ),
  td: ({ children }: { children?: ReactNode }) => <td className="px-4 py-3 align-top text-app-text">{children}</td>,
  code: ({ className, children }: { className?: string; children?: ReactNode }) =>
    className ? (
      <CodeBlock className={className}>{children}</CodeBlock>
    ) : (
      <code className="rounded-md bg-app-panel-soft px-1.5 py-0.5 text-[0.92em]">{children}</code>
    ),
  pre: ({ children }: { children?: ReactNode }) => <>{children}</>,
  a: ({ href, children }: { href?: string; children?: ReactNode }) => (
    <a className="text-app-accent-strong underline underline-offset-4" href={href} rel="noreferrer" target="_blank">
      {children}
    </a>
  ),
  strong: ({ children }: { children?: ReactNode }) => <strong className="font-semibold text-app-text">{children}</strong>,
};

function MarkdownMessageComponent({ content }: { content: string }) {
  const normalizedContent = useMemo(() => normalizeMarkdown(content), [content]);

  return (
    <ReactMarkdown
      components={markdownComponents}
      rehypePlugins={[rehypeKatex]}
      remarkPlugins={[remarkGfm, remarkMath]}
    >
      {normalizedContent}
    </ReactMarkdown>
  );
}

export const MarkdownMessage = memo(MarkdownMessageComponent);
