function resolveDefaultApiBase(): string {
  const explicit = import.meta.env.VITE_API_BASE?.trim();
  if (explicit) {
    return explicit;
  }

  if (typeof window === "undefined") {
    return "";
  }

  const { hostname, port, protocol } = window.location;
  const isLocalhost = hostname === "127.0.0.1" || hostname === "localhost";
  if (!isLocalhost || port !== "3300") {
    return "";
  }

  return `${protocol}//${hostname}:8050`;
}

const API_BASE = resolveDefaultApiBase();
let unauthorizedHandler: (() => void) | null = null;

export class ApiError extends Error {
  status: number;
  code: string | null;

  constructor(message: string, status: number, code: string | null = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

export function setUnauthorizedHandler(handler: (() => void) | null) {
  unauthorizedHandler = handler;
}

export function toApiUrl(path: string): string {
  if (!path.startsWith("/")) {
    return path;
  }
  return `${API_BASE}${path}`;
}

export async function readErrorPayload(response: Response): Promise<{ code: string | null; message: string }> {
  const raw = await response.text();
  if (!raw) {
    return {
      code: null,
      message: `Request failed: ${response.status}`,
    };
  }

  try {
    const parsed = JSON.parse(raw) as {
      code?: unknown;
      detail?: unknown;
      message?: unknown;
    };
    if (parsed.detail && typeof parsed.detail === "object") {
      const detail = parsed.detail as { code?: unknown; message?: unknown };
      if (typeof detail.message === "string" && detail.message.trim()) {
        return {
          code: typeof detail.code === "string" ? detail.code : null,
          message: detail.message,
        };
      }
    }
    if (typeof parsed.detail === "string" && parsed.detail.trim()) {
      return {
        code: typeof parsed.code === "string" ? parsed.code : null,
        message: parsed.detail,
      };
    }
    if (typeof parsed.message === "string" && parsed.message.trim()) {
      return {
        code: typeof parsed.code === "string" ? parsed.code : null,
        message: parsed.message,
      };
    }
  } catch {
    return {
      code: null,
      message: raw,
    };
  }

  return {
    code: null,
    message: raw,
  };
}

export async function assertApiResponse(response: Response): Promise<Response> {
  if (response.ok) {
    return response;
  }

  const { code, message } = await readErrorPayload(response);
  if (response.status === 401) {
    unauthorizedHandler?.();
  }
  throw new ApiError(message, response.status, code);
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(toApiUrl(path), {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  await assertApiResponse(response);

  return response.json() as Promise<T>;
}
