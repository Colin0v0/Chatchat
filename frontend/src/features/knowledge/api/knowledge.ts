import type {
  KnowledgeBatchDeleteResult,
  KnowledgeBatchMoveResult,
  KnowledgeBatchUploadResult,
  KnowledgeDocument,
  KnowledgeFolderDeleteResult,
  KnowledgeReindexResult,
  KnowledgeStatus,
} from "../../../types";
import { apiFetch, assertApiResponse, toApiUrl } from "../../../shared/api/http";

function withProjectQuery(path: string, projectId?: number | null) {
  if (!projectId) {
    return path;
  }
  const separator = path.includes("?") ? "&" : "?";
  return `${path}${separator}project_id=${encodeURIComponent(String(projectId))}`;
}

export function fetchKnowledgeFolders(projectId?: number | null) {
  return apiFetch<string[]>(withProjectQuery("/api/knowledge/folders", projectId));
}

export function createKnowledgeFolder(name: string, projectId?: number | null) {
  return apiFetch<string>(withProjectQuery("/api/knowledge/folders", projectId), {
    method: "POST",
    body: JSON.stringify({ name }),
  });
}

export function deleteKnowledgeFolder(name: string, projectId?: number | null) {
  return apiFetch<KnowledgeFolderDeleteResult>(withProjectQuery("/api/knowledge/folders", projectId), {
    method: "DELETE",
    body: JSON.stringify({ name }),
  });
}

export function renameKnowledgeFolder(name: string, newName: string, projectId?: number | null) {
  return apiFetch<string>(withProjectQuery("/api/knowledge/folders", projectId), {
    method: "PATCH",
    body: JSON.stringify({ name, new_name: newName }),
  });
}

export function fetchKnowledgeDocuments(projectId?: number | null) {
  return apiFetch<KnowledgeDocument[]>(withProjectQuery("/api/knowledge/documents", projectId));
}

export function fetchKnowledgeStatus(projectId?: number | null) {
  return apiFetch<KnowledgeStatus>(withProjectQuery("/api/knowledge/status", projectId));
}

export async function uploadKnowledgeDocuments(
  files: File[],
  options: { folder?: string; projectId?: number | null; relativePaths?: string[] } = {},
) {
  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));
  if (options.folder) {
    formData.append("folder", options.folder);
  }
  options.relativePaths?.forEach((relativePath) => formData.append("relative_paths", relativePath));
  if (options.projectId) {
    formData.append("project_id", String(options.projectId));
  }

  const response = await fetch(toApiUrl("/api/knowledge/documents/batch"), {
    credentials: "include",
    method: "POST",
    body: formData,
  });
  await assertApiResponse(response);
  return response.json() as Promise<KnowledgeBatchUploadResult>;
}

export function reindexKnowledgeDocument(documentId: number, projectId?: number | null) {
  return apiFetch<KnowledgeDocument>(withProjectQuery(`/api/knowledge/documents/${documentId}/reindex`, projectId), {
    method: "POST",
  });
}

export function reindexKnowledgeDocuments(projectId?: number | null) {
  return apiFetch<KnowledgeReindexResult>(withProjectQuery("/api/knowledge/reindex", projectId), {
    method: "POST",
  });
}

export async function deleteKnowledgeDocument(documentId: number, projectId?: number | null) {
  const response = await fetch(toApiUrl(withProjectQuery(`/api/knowledge/documents/${documentId}`, projectId)), {
    credentials: "include",
    method: "DELETE",
  });
  await assertApiResponse(response);
}

export function deleteKnowledgeDocuments(documentIds: number[], projectId?: number | null) {
  return apiFetch<KnowledgeBatchDeleteResult>(withProjectQuery("/api/knowledge/documents/delete", projectId), {
    method: "POST",
    body: JSON.stringify({ document_ids: documentIds }),
  });
}

export function moveKnowledgeDocuments(documentIds: number[], folder: string, projectId?: number | null) {
  return apiFetch<KnowledgeBatchMoveResult>(withProjectQuery("/api/knowledge/documents/folder", projectId), {
    method: "PATCH",
    body: JSON.stringify({ document_ids: documentIds, folder }),
  });
}
