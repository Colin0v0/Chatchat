import type { ChatStreamEvent, ImageGenerationJob, ImageGenerationRequest } from "../../../types";
import { apiFetch } from "../../../shared/api/http";

export interface ImageGenerationRequestOptions {
  onEvent: (event: ChatStreamEvent) => void;
  signal?: AbortSignal;
  batchWindowMs?: number;
}

export function startImageGenerationJob(payload: ImageGenerationRequest, signal?: AbortSignal) {
  return apiFetch<ImageGenerationJob>("/api/images/jobs", {
    method: "POST",
    body: JSON.stringify(payload),
    signal,
  });
}

export function fetchImageGenerationJob(jobId: number, signal?: AbortSignal) {
  return apiFetch<ImageGenerationJob>(`/api/images/jobs/${jobId}`, { signal });
}

function waitForNextPoll(milliseconds: number, signal?: AbortSignal) {
  if (signal?.aborted) {
    throw new DOMException("Request aborted.", "AbortError");
  }

  return new Promise<void>((resolve, reject) => {
    let timeoutId: number;
    const handleAbort = () => {
      window.clearTimeout(timeoutId);
      cleanup();
      reject(new DOMException("Request aborted.", "AbortError"));
    };
    const cleanup = () => signal?.removeEventListener("abort", handleAbort);
    timeoutId = window.setTimeout(() => {
      cleanup();
      resolve();
    }, milliseconds);
    signal?.addEventListener("abort", handleAbort, { once: true });
  });
}

export async function pollImageGenerationJob(
  payload: ImageGenerationRequest,
  options: ImageGenerationRequestOptions & { model: string },
) {
  const job = await startImageGenerationJob(payload, options.signal);
  options.onEvent({
    type: "meta",
    conversation_id: job.conversation_id,
    message_id: job.user_message_id,
    model: options.model,
  });
  options.onEvent({ type: "status", items: ["Generating image"] });

  let current = job;
  while (current.status === "queued" || current.status === "running") {
    // 轮询请求很短，Cloudflare 橙云不会再被一个长 POST 卡住。
    await waitForNextPoll(current.status === "queued" ? 1200 : 2200, options.signal);
    current = await fetchImageGenerationJob(job.job_id, options.signal);
  }

  if (current.status === "failed") {
    options.onEvent({
      type: "error",
      message: current.error_message ?? "",
    });
    return;
  }

  options.onEvent({
    type: "done",
    assistant_message_id: current.assistant_message_id ?? undefined,
    conversation_title: current.conversation_title,
    content: current.content,
  });
}
