import type { ChatStreamEvent, ImageGenerationRequest } from "../../../types";
import { assertApiResponse, toApiUrl } from "../../../shared/api/http";
import { consumeNdjsonStream } from "../../../shared/api/ndjson";

export interface ImageGenerationRequestOptions {
  onEvent: (event: ChatStreamEvent) => void;
  signal?: AbortSignal;
  batchWindowMs?: number;
}

export async function generateImage(
  payload: ImageGenerationRequest,
  options: ImageGenerationRequestOptions,
) {
  const response = await fetch(toApiUrl("/api/images/generate"), {
    credentials: "include",
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
    signal: options.signal,
  });
  await assertApiResponse(response);

  await consumeNdjsonStream<ChatStreamEvent>(response, options.onEvent, options.batchWindowMs);
}
