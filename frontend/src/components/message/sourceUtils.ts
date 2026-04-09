import type { MessageSource } from "../../types";

export interface SourceGroup {
  key: "note" | "file" | "web";
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
  if (source.type === "file" && trimmed) {
    return `/media/${trimmed.replace(/^\/+/, "")}`;
  }
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
    return "Web source";
  }
  if (source.type === "file") {
    return source.title?.trim() || source.path;
  }
  return source.path;
}

export function getSourceMeta(source: MessageSource): string | null {
  if (source.type === "web") {
    return source.url?.trim() || source.path.trim() || null;
  }

  if (source.type === "file") {
    return source.heading ? source.heading : null;
  }

  return source.heading ? source.heading : null;
}

export function groupSources(sources: MessageSource[]): SourceGroup[] {
  const notes = sources.filter((source) => source.type === "note" || source.type == null);
  const files = sources.filter((source) => source.type === "file");
  const web = sources.filter((source) => source.type === "web");
  const groups: SourceGroup[] = [];
  if (notes.length > 0) {
    groups.push({ key: "note", label: "RAG source", items: notes });
  }
  if (files.length > 0) {
    groups.push({ key: "file", label: "File source", items: files });
  }
  if (web.length > 0) {
    groups.push({ key: "web", label: "Web source", items: web });
  }
  return groups;
}
