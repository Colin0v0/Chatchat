import { isRecord, readBrowserCache, writeBrowserCache } from "../../../shared/lib/browserCache";
import { isModelsPayload } from "../../models/lib/modelOptionGuards";
import type { ConversationSummary, DebateSessionSummary, ModelsPayload } from "../../../types";

const CONVERSATION_SUMMARIES_CACHE_STORAGE_KEY = "chatchat.cache.conversation-summaries.v1";
const DEBATE_SUMMARIES_CACHE_STORAGE_KEY = "chatchat.cache.debate-summaries.v1";
const MODELS_CACHE_STORAGE_KEY = "chatchat.cache.models.v1";

function isConversationSummary(value: unknown): value is ConversationSummary {
  return (
    isRecord(value)
    && typeof value.id === "number"
    && typeof value.title === "string"
    && typeof value.model === "string"
    && (typeof value.temporary_chat === "boolean" || value.temporary_chat === undefined)
    && (typeof value.updated_at === "string" || value.updated_at === null)
    && typeof value.last_message_preview === "string"
  );
}

function isDebateSessionSummary(value: unknown): value is DebateSessionSummary {
  return (
    isRecord(value)
    && typeof value.id === "number"
    && typeof value.topic === "string"
    && typeof value.status === "string"
    && typeof value.stage === "string"
    && (typeof value.updated_at === "string" || value.updated_at === null)
    && typeof value.last_turn_preview === "string"
  );
}

export function loadStoredConversationSummariesCache(): ConversationSummary[] | null {
  return readBrowserCache(
    CONVERSATION_SUMMARIES_CACHE_STORAGE_KEY,
    (value): value is ConversationSummary[] => Array.isArray(value) && value.every(isConversationSummary),
  );
}

export function loadStoredDebateSummariesCache(): DebateSessionSummary[] | null {
  return readBrowserCache(
    DEBATE_SUMMARIES_CACHE_STORAGE_KEY,
    (value): value is DebateSessionSummary[] => Array.isArray(value) && value.every(isDebateSessionSummary),
  );
}

export function loadStoredModelsCache(): ModelsPayload | null {
  return readBrowserCache(MODELS_CACHE_STORAGE_KEY, isModelsPayload);
}

export function saveConversationSummariesCache(items: ConversationSummary[]) {
  // 移动端和桌面端共用浏览器缓存：先秒开旧列表，再用服务器结果覆盖。
  writeBrowserCache(CONVERSATION_SUMMARIES_CACHE_STORAGE_KEY, items);
}

export function saveDebateSummariesCache(items: DebateSessionSummary[]) {
  writeBrowserCache(DEBATE_SUMMARIES_CACHE_STORAGE_KEY, items);
}

export function saveModelsCache(payload: ModelsPayload) {
  writeBrowserCache(MODELS_CACHE_STORAGE_KEY, payload);
}
