function isLoopbackHostname(hostname: string): boolean {
  return hostname === "127.0.0.1" || hostname === "localhost";
}

function isProxyFrontendPort(port: string): boolean {
  return port === "3300" || port === "5200";
}

function resolveDefaultApiBase(): string {
  if (typeof window === "undefined") {
    return "";
  }

  const explicit = import.meta.env.VITE_API_BASE?.trim();
  const { hostname, port, protocol } = window.location;

  if (explicit) {
    try {
      const explicitUrl = new URL(explicit);
      // When a mobile device opens a frontend that proxies /api and /media,
      // a loopback API base would point back to the phone itself and break
      // image/media loading. Fall back to same-origin relative paths instead.
      if (isProxyFrontendPort(port) && !isLoopbackHostname(hostname) && isLoopbackHostname(explicitUrl.hostname)) {
        return "";
      }
    } catch {
      return explicit;
    }
    return explicit;
  }

  if (isProxyFrontendPort(port)) {
    return "";
  }

  if (isLoopbackHostname(hostname)) {
    return `${protocol}//${hostname}:8050`;
  }

  return "";
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
  const method = (init?.method ?? "GET").toUpperCase();
  const shouldSendJsonContentType =
    init?.body !== undefined &&
    init?.body !== null &&
    method !== "GET" &&
    method !== "DELETE" &&
    !(init.body instanceof FormData);
  const response = await fetch(toApiUrl(path), {
    credentials: "include",
    ...init,
    headers: {
      ...(shouldSendJsonContentType ? { "Content-Type": "application/json" } : {}),
      ...(init?.headers ?? {}),
    },
  });

  await assertApiResponse(response);

  return response.json() as Promise<T>;
}
