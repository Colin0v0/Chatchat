import type { ProjectSummary } from "../../../types";
import { apiFetch, assertApiResponse, toApiUrl } from "../../../shared/api/http";

export function fetchProjects() {
  return apiFetch<ProjectSummary[]>("/api/projects");
}

export function createProject(payload: {
  name: string;
  description?: string;
  default_model?: string | null;
}) {
  return apiFetch<ProjectSummary>("/api/projects", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateProject(
  projectId: number,
  payload: Partial<Pick<ProjectSummary, "name" | "description" | "default_model">>,
) {
  return apiFetch<ProjectSummary>(`/api/projects/${projectId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function deleteProject(projectId: number) {
  const response = await fetch(toApiUrl(`/api/projects/${projectId}`), {
    credentials: "include",
    method: "DELETE",
  });
  await assertApiResponse(response);
}
