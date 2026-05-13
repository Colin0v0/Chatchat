import type { ChatMessage, ModelOption, ToolMode } from "../../../types";

const IMAGE_ATTACHMENT_EXTENSIONS = new Set([".gif", ".jpeg", ".jpg", ".png", ".webp"]);

function fileExtension(name: string) {
  const dotIndex = name.lastIndexOf(".");
  return dotIndex >= 0 ? name.slice(dotIndex).toLowerCase() : "";
}

export function fileLooksLikeImage(file: File) {
  return file.type.startsWith("image/") || IMAGE_ATTACHMENT_EXTENSIONS.has(fileExtension(file.name));
}

export function modelAllowsImageAttachments(model: ModelOption) {
  return model.capabilities?.input.image ?? model.supports_attachment_upload;
}

export function toggleToolMode(current: ToolMode, next: Exclude<ToolMode, "none">): ToolMode {
  return current === next ? "none" : next;
}

export const PET_CONTEXT_MESSAGE_LIMIT = 8;
export const PET_CONTEXT_TEXT_LIMIT = 420;

export function compactPetContextText(text: string) {
  return text.replace(/\s+/g, " ").trim().slice(0, PET_CONTEXT_TEXT_LIMIT);
}

export function toPetContextMessages(messages: ChatMessage[]) {
  return messages
    .filter((message) => message.role === "user" || message.role === "assistant" || message.role === "system")
    .map((message) => ({
      content: compactPetContextText(message.content),
      role: message.role,
    }))
    .filter((message) => message.content.length > 0)
    .slice(-PET_CONTEXT_MESSAGE_LIMIT);
}
