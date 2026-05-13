import { Brain, ChevronRight, Database, Globe, ScrollText } from "lucide-react";
import { useMemo, useState, type ReactNode } from "react";

import type {
  MessageContext,
  MessageContextSection,
  MessageMemoryDocumentReference,
  MessageMemoryReference,
  MessagePastChatReference,
  MessageSource,
  SearchTrace,
} from "../../../../types";

interface MessageReferencesPanelProps {
  context: MessageContext | null;
  searchTrace: SearchTrace | null;
  sources: MessageSource[];
}

type ReferenceGroupKey = "web" | "rag" | "context" | "memory";

interface ReferenceGroup {
  key: ReferenceGroupKey;
  label: string;
  count: number;
  content: ReactNode;
}

function sourceKey(source: MessageSource, index: number) {
  return [source.type ?? "note", source.url ?? "", source.path ?? "", source.heading ?? "", index].join(":");
}

function compactText(value: string, limit = 180) {
  const normalized = value.replace(/\s+/g, " ").trim();
  if (normalized.length <= limit) {
    return normalized;
  }
  return `${normalized.slice(0, limit - 1)}...`;
}

function contextSectionBody(section: MessageContextSection) {
  return section.body
    .replace(/另外参考了\d+条记忆信息。?/g, "")
    .replace(/另外参考了\d+条外部资料。?/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

function visibleMemoryDocuments(context: MessageContext) {
  return (context.memory_documents ?? []).filter((document) => document.doc_type !== "conversation_brief");
}

function visibleMemoryCount(context: MessageContext) {
  const itemCount = context.memory_items?.length ?? 0;
  const documentCount = visibleMemoryDocuments(context).length;
  if (context.memory_items || context.memory_documents) {
    return itemCount + documentCount;
  }
  return context.memory_count;
}

function memoryDocumentTitle(document: MessageMemoryDocumentReference) {
  switch (document.doc_type) {
    case "user_profile":
      return "用户画像摘要";
    case "workspace_profile":
      return "工作区摘要";
    case "conversation_brief":
      return "当前会话摘要";
  }
}

function compactMultilineText(value: string, limit = 320) {
  const normalized = value
    .split("\n")
    .map((line) => line.replace(/\s+/g, " ").trim())
    .filter(Boolean)
    .join("\n");
  if (normalized.length <= limit) {
    return normalized;
  }
  return `${normalized.slice(0, limit - 1)}...`;
}

function memoryDocumentContent(document: MessageMemoryDocumentReference) {
  const lines = document.content
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
  const cleanedLines = lines
    .filter(
      (line) =>
        !line.startsWith("Current thread brief.") &&
        !line.startsWith("Stable user profile.") &&
        !line.startsWith("Persistent workspace context shared"),
    )
    .map((line) =>
      line
        .replace(/^Fact:\s*$/i, "事实")
        .replace(/^Profile:\s*$/i, "画像")
        .replace(/^Preference:\s*$/i, "偏好")
        .replace(/^Goal:\s*$/i, "目标")
        .replace(/^Project:\s*$/i, "项目")
        .replace(/^Constraint:\s*$/i, "约束")
        .replace(/^- \[inferred\]\s*/i, "- 推断：")
        .replace(/^- \[confirmed\]\s*/i, "- 已确认：")
        .replace(/\s+::\s+/g, "：")
        .replace(/\s+\[evidence \d+\]/gi, ""),
    );
  return compactMultilineText(cleanedLines.join("\n"));
}

function uniqueWebSources(sources: MessageSource[], trace: SearchTrace | null) {
  const seen = new Set<string>();
  const items: MessageSource[] = [];
  [...sources.filter((source) => source.type === "web"), ...(trace?.sources ?? [])].forEach((source, index) => {
    const key = source.url?.trim() || source.path?.trim() || source.title?.trim() || `web-${index}`;
    if (seen.has(key)) {
      return;
    }
    seen.add(key);
    items.push(source);
  });
  return items;
}

function WebContent({ sources }: { sources: MessageSource[] }) {
  return (
    <div className="space-y-3">
      {sources.length > 0 ? (
        <div className="space-y-2">
          {sources.slice(0, 8).map((source, index) => {
            const title = source.title?.trim() || source.heading?.trim() || source.domain?.trim() || source.url?.trim() || "网页来源";
            const url = source.url?.trim();
            const meta = source.domain?.trim() || url || source.path;
            return (
              <div className="min-w-0 rounded-[8px] border border-app-border bg-white px-3 py-2" key={sourceKey(source, index)}>
                <div className="break-words text-[13px] font-medium leading-5 text-app-text">{title}</div>
                {meta ? (
                  url ? (
                    <a
                      className="mt-1 block break-all text-[12px] leading-5 text-app-muted underline-offset-2 hover:text-app-text hover:underline"
                      href={url}
                      rel="noreferrer"
                      target="_blank"
                    >
                      {meta}
                    </a>
                  ) : (
                    <div className="mt-1 break-all text-[12px] leading-5 text-app-muted">{meta}</div>
                  )
                ) : null}
                {source.excerpt ? (
                  <div className="mt-1 break-words text-[12px] leading-5 text-app-muted/85">
                    {compactText(source.excerpt)}
                  </div>
                ) : null}
              </div>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}

function RagContent({ sources }: { sources: MessageSource[] }) {
  return (
    <div className="space-y-2">
      {sources.slice(0, 8).map((source, index) => {
        const title = source.title?.trim() || source.path || "知识库来源";
        const heading = source.heading?.trim();
        return (
          <div className="min-w-0 rounded-[8px] border border-app-border bg-white px-3 py-2" key={sourceKey(source, index)}>
            <div className="break-words text-[13px] font-medium leading-5 text-app-text">{title}</div>
            {heading ? <div className="mt-1 break-words text-[12px] leading-5 text-app-muted">{heading}</div> : null}
            {source.excerpt ? (
              <div className="mt-1 break-words text-[12px] leading-5 text-app-muted/85">
                {compactText(source.excerpt)}
              </div>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}

function ContextContent({ context }: { context: MessageContext }) {
  const summarySections = context.sections
    .map((section) => ({ ...section, body: contextSectionBody(section) }))
    .filter((section) => section.body.length > 0);
  const contextCards: Array<{ title: string; detail: string }> = [];
  if (context.recent_message_count > 0) {
    contextCards.push({
      title: "最近上下文",
      detail: `本轮回答读取了最近 ${context.recent_message_count} 轮对话。`,
    });
  }
  if (context.older_message_count > 0) {
    contextCards.push({
      title: "压缩历史",
      detail: `更早的 ${context.older_message_count} 轮对话已压缩后注入。`,
    });
  }
  const shouldShowSummarySections = contextCards.length === 0;

  return (
    <div className="space-y-2">
      {contextCards.length > 0 ? (
        <div className="space-y-2">
          {contextCards.map((item) => (
            <div className="min-w-0 rounded-[8px] border border-app-border bg-white px-3 py-2" key={item.title}>
              <div className="break-words text-[13px] font-medium leading-5 text-app-text">{item.title}</div>
              <div className="mt-1 break-words text-[12px] leading-5 text-app-muted">{item.detail}</div>
            </div>
          ))}
        </div>
      ) : null}
      {shouldShowSummarySections ? summarySections.map((section) => (
        <div className="min-w-0 rounded-[8px] border border-app-border bg-white px-3 py-2" key={`${section.kind}-${section.title}`}>
          <div className="break-words text-[13px] font-medium leading-5 text-app-text">上下文说明</div>
          <div className="mt-1 whitespace-pre-wrap break-words text-[12px] leading-5 text-app-muted">
            {section.body}
          </div>
        </div>
      )) : null}
    </div>
  );
}

function MemoryItemLine({ item }: { item: MessageMemoryReference }) {
  return (
    <div className="rounded-[8px] border border-app-border bg-white px-3 py-2">
      <div className="flex min-w-0 flex-wrap items-center gap-2">
        <span className="break-words text-[13px] font-medium leading-5 text-app-text">{item.title}</span>
        <span className="rounded-[6px] bg-app-panel-soft px-1.5 py-0.5 text-[11px] text-app-muted">
          {item.scope === "global" ? "长期" : item.scope === "working" ? "工作中" : "对话"}
        </span>
        <span className="rounded-[6px] bg-app-panel-soft px-1.5 py-0.5 text-[11px] text-app-muted">
          {item.confidence_state === "confirmed" ? "已确认" : "推断"}
        </span>
      </div>
      {item.detail ? <div className="mt-1 break-words text-[12px] leading-5 text-app-muted">{item.detail}</div> : null}
    </div>
  );
}

function MemoryDocumentLine({ document }: { document: MessageMemoryDocumentReference }) {
  const content = memoryDocumentContent(document);
  return (
    <div className="rounded-[8px] border border-app-border bg-white px-3 py-2">
      <div className="break-words text-[13px] font-medium leading-5 text-app-text">{memoryDocumentTitle(document)}</div>
      {content ? (
        <div className="mt-1 whitespace-pre-wrap break-words text-[12px] leading-5 text-app-muted">
          {content}
        </div>
      ) : null}
    </div>
  );
}

function PastChatLine({ reference }: { reference: MessagePastChatReference }) {
  const title = reference.conversation_title?.trim() || `历史会话 ${reference.conversation_id}`;
  const content = reference.summary?.trim() || reference.excerpt?.trim();
  return (
    <div className="rounded-[8px] border border-app-border bg-white px-3 py-2">
      <div className="break-words text-[13px] font-medium leading-5 text-app-text">{title}</div>
      {content ? <div className="mt-1 break-words text-[12px] leading-5 text-app-muted">{compactText(content, 220)}</div> : null}
    </div>
  );
}

function MemoryContent({ context }: { context: MessageContext }) {
  const items = context.memory_items ?? [];
  const documents = visibleMemoryDocuments(context);
  const pastChats = context.past_chats ?? [];
  return (
    <div className="space-y-2">
      {items.map((item) => (
        <MemoryItemLine item={item} key={`item-${item.id}`} />
      ))}
      {documents.map((document) => (
        <MemoryDocumentLine document={document} key={`doc-${document.id}`} />
      ))}
      {pastChats.map((reference) => (
        <PastChatLine key={`past-${reference.id}`} reference={reference} />
      ))}
      {items.length === 0 && documents.length === 0 && pastChats.length === 0 && context.memory_count > 0 ? (
        <div className="rounded-[8px] border border-app-border bg-white px-3 py-2 text-[13px] leading-6 text-app-muted">
          本轮实际注入了 {context.memory_count} 条记忆。
        </div>
      ) : null}
    </div>
  );
}

function groupIcon(key: ReferenceGroupKey) {
  if (key === "web") {
    return <Globe className="size-4" />;
  }
  if (key === "rag") {
    return <Database className="size-4" />;
  }
  if (key === "memory") {
    return <Brain className="size-4" />;
  }
  return <ScrollText className="size-4" />;
}

export function MessageReferencesPanel({ context, searchTrace, sources }: MessageReferencesPanelProps) {
  const [expanded, setExpanded] = useState(false);
  const groups = useMemo<ReferenceGroup[]>(() => {
    const nextGroups: ReferenceGroup[] = [];
    const webSources = uniqueWebSources(sources, searchTrace);
    const ragSources = sources.filter((source) => source.type === "note" || source.type == null);

    if (webSources.length > 0) {
      nextGroups.push({
        key: "web",
        label: "Web",
        count: webSources.length,
        content: <WebContent sources={webSources} />,
      });
    }

    if (ragSources.length > 0) {
      nextGroups.push({
        key: "rag",
        label: "RAG",
        count: ragSources.length,
        content: <RagContent sources={ragSources} />,
      });
    }

    if (context && (context.sections.some((section) => section.body.trim().length > 0) || context.recent_message_count > 0)) {
      const contextCount =
        (context.recent_message_count > 0 ? 1 : 0) +
        (context.older_message_count > 0 ? 1 : 0) ||
        context.sections.filter((section) => section.body.trim().length > 0).length;
      nextGroups.push({
        key: "context",
        label: "Context",
        count: contextCount,
        content: <ContextContent context={context} />,
      });
    }

    const memoryCount = context ? visibleMemoryCount(context) : 0;
    const pastChatCount = context?.past_chats?.length ?? 0;
    if (context && memoryCount + pastChatCount > 0) {
      nextGroups.push({
        key: "memory",
        label: "Memory",
        count: memoryCount + pastChatCount,
        content: <MemoryContent context={context} />,
      });
    }

    return nextGroups;
  }, [context, searchTrace, sources]);

  if (groups.length === 0) {
    return null;
  }

  return (
    <section className="mt-4">
      <button
        aria-expanded={expanded}
        className="inline-flex items-center gap-2 rounded-lg py-1 text-[13px] text-app-muted/85 transition hover:text-app-text"
        onClick={() => setExpanded((value) => !value)}
        type="button"
      >
        <span>本次参考</span>
        <span className="text-app-muted/65">
          {groups.map((group) => `${group.label} ${group.count}`).join(" · ")}
        </span>
        <ChevronRight className={`size-4 transition-transform duration-200 ${expanded ? "rotate-90" : ""}`} />
      </button>

      <div
        className={`grid transition-[grid-template-rows,opacity,margin] duration-200 ${
          expanded ? "mt-3 grid-rows-[1fr] opacity-100" : "mt-0 grid-rows-[0fr] opacity-0"
        }`}
      >
        <div className="overflow-hidden">
          <div className="space-y-3 rounded-[12px] border border-app-border bg-app-panel-strong/70 px-4 py-4">
            {groups.map((group) => (
              <section key={group.key}>
                <div className="mb-2 flex items-center gap-2 text-[13px] font-medium text-app-muted">
                  {groupIcon(group.key)}
                  <span>{group.label}</span>
                  <span className="text-[12px] font-normal text-app-muted/70">{group.count}</span>
                </div>
                {group.content}
              </section>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
