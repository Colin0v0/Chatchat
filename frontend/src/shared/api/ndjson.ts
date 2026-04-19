export function parseNdjsonEvent<TEvent>(raw: string): TEvent | null {
  const trimmed = raw.trim();
  if (!trimmed) {
    return null;
  }

  try {
    return JSON.parse(trimmed) as TEvent;
  } catch (err) {
    console.warn("[ndjson parse error]", trimmed.substring(0, 100), err);
    return null;
  }
}

export function createBatchedEventDispatcher<TEvent>(
  onEvent: (event: TEvent) => void,
  batchWindowMs = 0,
) {
  let timerId: number | null = null;
  let pendingEvents: TEvent[] = [];

  const flush = () => {
    timerId = null;
    if (!pendingEvents.length) {
      return;
    }
    const batch = pendingEvents;
    pendingEvents = [];
    for (const event of batch) {
      onEvent(event);
    }
  };

  return {
    dispatch(event: TEvent) {
      if (batchWindowMs <= 0) {
        onEvent(event);
        return;
      }
      pendingEvents.push(event);
      if (timerId !== null) {
        return;
      }
      timerId = window.setTimeout(flush, batchWindowMs);
    },
    finish() {
      if (timerId !== null) {
        window.clearTimeout(timerId);
        timerId = null;
      }
      flush();
    },
  };
}

export async function consumeNdjsonStream<TEvent>(
  response: Response,
  onEvent: (event: TEvent) => void,
  batchWindowMs = 0,
) {
  if (!response.body) {
    throw new Error("Streaming is not supported by this browser.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  const dispatcher = createBatchedEventDispatcher(onEvent, batchWindowMs);
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";

      for (const line of lines) {
        const event = parseNdjsonEvent<TEvent>(line);
        if (event) {
          dispatcher.dispatch(event);
        }
      }
    }

    buffer += decoder.decode();
    const tailEvent = parseNdjsonEvent<TEvent>(buffer);
    if (tailEvent) {
      dispatcher.dispatch(tailEvent);
    }
  } finally {
    dispatcher.finish();
  }
}
