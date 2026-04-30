import type { BattleStreamRequest, ChatStreamEvent } from "../../../types";
import { assertApiResponse, toApiUrl } from "../../../shared/api/http";
import { consumeNdjsonStream } from "../../../shared/api/ndjson";

export interface BattleStreamOptions {
  onEvent: (event: ChatStreamEvent) => void;
  signal?: AbortSignal;
}

export async function streamBattleResponse(payload: BattleStreamRequest, options: BattleStreamOptions) {
  const formData = new FormData();
  formData.append("message", payload.message);
  formData.append("model", payload.model);
  formData.append("tool_mode", payload.tool_mode);
  if (payload.history && payload.history.length > 0) {
    formData.append("history", JSON.stringify(payload.history));
  }
  payload.knowledge_folders?.forEach((folder) => formData.append("knowledge_folders", folder));
  if (payload.reasoning_profile) {
    formData.append("reasoning_profile", payload.reasoning_profile);
  }
  payload.files?.forEach((file) => formData.append("files", file));

  const response = await fetch(toApiUrl("/api/battle/stream"), {
    credentials: "include",
    method: "POST",
    body: formData,
    signal: options.signal,
  });
  await assertApiResponse(response);

  await consumeNdjsonStream<ChatStreamEvent>(response, options.onEvent);
}
