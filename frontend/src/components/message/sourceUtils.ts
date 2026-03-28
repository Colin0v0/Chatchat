import type { MessageSource } from "../../types";

const HIDDEN_BADGES = new Set(["standard", "unknown"]);

export interface SourceGroup {
  key: "note" | "web";
  label: string;
  items: MessageSource[];
}

export function formatScore(score: number | null | undefined): string | null {
  if (typeof score !== "number" || Number.isNaN(score)) {
    return null;
  }
  return score.toFixed(2);
}

export function toSourceHref(source: MessageSource): string {
  const directUrl = source.url?.trim();
  if (directUrl) {
    return directUrl;
  }

  const trimmed = source.path.trim();
  if (/^[a-zA-Z]:[\\/]/.test(trimmed)) {
    return `file:///${trimmed.replace(/\\/g, "/")}`;
  }
  if (trimmed.startsWith("/")) {
    return `file://${trimmed}`;
  }
  return `obsidian://open?file=${encodeURIComponent(trimmed)}`;
}

export function getSourceLabel(source: MessageSource): string {
  if (source.type === "web") {
    return source.title?.trim() || source.domain?.trim() || source.url?.trim() || source.path;
  }
  return source.path;
}

export function getSourceMeta(source: MessageSource): string | null {
  if (source.type === "web") {
    const parts = [source.domain, source.published_at].map((item) => item?.trim()).filter(Boolean);
    return parts.length > 0 ? parts.join(" - ") : null;
  }

  return source.heading ? source.heading : null;
}

export function getSourceBadges(source: MessageSource): string[] {
  return [source.trust, source.freshness]
    .map((item) => item?.trim())
    .filter(
      (item): item is string =>
        typeof item === "string" && item.length > 0 && !HIDDEN_BADGES.has(item.toLowerCase()),
    );
}

export function groupSources(sources: MessageSource[]): SourceGroup[] {
  const notes = sources.filter((source) => source.type !== "web");
  const web = sources.filter((source) => source.type === "web");
  const groups: SourceGroup[] = [];
  if (notes.length > 0) {
    groups.push({ key: "note", label: "RAG Sources", items: notes });
  }
  if (web.length > 0) {
    groups.push({ key: "web", label: "Web Sources", items: web });
  }
  return groups;
}
