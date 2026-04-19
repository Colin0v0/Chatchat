import type { AuthSession } from "../../../types";
import { apiFetch, assertApiResponse, toApiUrl } from "../../../shared/api/http";

export function fetchSession(options?: { signal?: AbortSignal }) {
  return apiFetch<AuthSession>("/api/auth/session", {
    signal: options?.signal,
  });
}

export async function login(payload: { username: string; password: string }) {
  const response = await fetch(toApiUrl("/api/auth/login"), {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
    },
    method: "POST",
    body: JSON.stringify(payload),
  });
  await assertApiResponse(response);

  return response.json() as Promise<AuthSession>;
}

export async function logout() {
  const response = await fetch(toApiUrl("/api/auth/logout"), {
    credentials: "include",
    method: "POST",
  });
  await assertApiResponse(response);
}
