export const ASSISTANT_DRAFT_ID = "assistant-draft";
export const INITIAL_CHAT_MODEL = "openai:deepseek-chat";
export const INITIAL_REASONING_MODEL = "openai:deepseek-reasoner";

const FILTER_PATTERN = /\b(?:folder|tag|path):\S+/gi;
const TITLE_MAX_LENGTH = 40;

const LANDING_TITLES = [
  "你好同志，请问有需要帮助的吗？",
  "今天想让模型帮你做什么？",
  "这次想先解决哪个问题？",
  "给我一个目标，我来帮你拆。",
  "今天这件事，我们从哪一步开始？",
] as const;

export function pickLandingTitle() {
  return LANDING_TITLES[Math.floor(Math.random() * LANDING_TITLES.length)];
}

export function deriveConversationTitle(content: string, attachmentCount: number) {
  const normalized = content.replace(FILTER_PATTERN, "").replace(/\s+/g, " ").trim();
  const candidate = normalized.split(/[\n。！？.!?,，]/, 1)[0]?.trim() ?? "";
  if (candidate) {
    return candidate.length <= TITLE_MAX_LENGTH ? candidate : `${candidate.slice(0, TITLE_MAX_LENGTH - 1).trim()}…`;
  }
  if (attachmentCount > 0) {
    return attachmentCount === 1 ? "Attachment Analysis" : `${attachmentCount} Attachments`;
  }
  return "New chat";
}
