import type { MemoryDocument, MemoryItem, MemoryKind, MemoryScope } from "../../../types";

export const MEMORY_KIND_LABELS: Record<MemoryKind, string> = {
  profile: "身份",
  preference: "偏好",
  goal: "目标",
  project: "项目",
  fact: "事实",
  constraint: "约束",
};

export const MEMORY_SCOPE_LABELS: Record<MemoryScope, string> = {
  global: "长期",
  conversation: "会话",
  working: "工作中",
};

export const MEMORY_SOURCE_LABELS: Record<string, string> = {
  auto: "系统识别",
  manual: "手动添加",
  promoted: "主动记住",
};

export const MEMORY_CONFIDENCE_STATE_LABELS: Record<MemoryItem["confidence_state"], string> = {
  pending: "待确认",
  inferred: "推断",
  confirmed: "确认",
  rejected: "已拒绝",
};

export const DOCUMENT_LABELS: Record<MemoryDocument["doc_type"], string> = {
  user_profile: "用户画像",
  workspace_profile: "工作区画像",
  conversation_brief: "会话画像",
};

export function formatMemoryTimestamp(value: string | null): string {
  if (!value) {
    return "未记录";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "未记录";
  }
  return new Intl.DateTimeFormat("zh-CN", {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export function formatMemorySource(value: string): string {
  return MEMORY_SOURCE_LABELS[value] ?? value;
}

export function formatMemoryConfidence(value: number): string {
  return `${Math.round(value * 100)}%`;
}
