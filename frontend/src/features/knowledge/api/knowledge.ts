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

export function fetchKnowledgeFolders() {
  return apiFetch<string[]>("/api/knowledge/folders");
}

export function createKnowledgeFolder(name: string) {
  return apiFetch<string>("/api/knowledge/folders", {
    method: "POST",
    body: JSON.stringify({ name }),
  });
}

export function deleteKnowledgeFolder(name: string) {
  return apiFetch<KnowledgeFolderDeleteResult>("/api/knowledge/folders", {
    method: "DELETE",
    body: JSON.stringify({ name }),
  });
}

export function fetchKnowledgeDocuments() {
  return apiFetch<KnowledgeDocument[]>("/api/knowledge/documents");
}

export function fetchKnowledgeStatus() {
  return apiFetch<KnowledgeStatus>("/api/knowledge/status");
}

export async function uploadKnowledgeDocuments(
  files: File[],
  options: { folder?: string; relativePaths?: string[] } = {},
) {
  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));
  if (options.folder) {
    formData.append("folder", options.folder);
  }
  options.relativePaths?.forEach((relativePath) => formData.append("relative_paths", relativePath));

  const response = await fetch(toApiUrl("/api/knowledge/documents/batch"), {
    credentials: "include",
    method: "POST",
    body: formData,
  });
  await assertApiResponse(response);
  return response.json() as Promise<KnowledgeBatchUploadResult>;
}

export function reindexKnowledgeDocument(documentId: number) {
  return apiFetch<KnowledgeDocument>(`/api/knowledge/documents/${documentId}/reindex`, {
    method: "POST",
  });
}

export function reindexKnowledgeDocuments() {
  return apiFetch<KnowledgeReindexResult>("/api/knowledge/reindex", {
    method: "POST",
  });
}

export async function deleteKnowledgeDocument(documentId: number) {
  const response = await fetch(toApiUrl(`/api/knowledge/documents/${documentId}`), {
    credentials: "include",
    method: "DELETE",
  });
  await assertApiResponse(response);
}

export function deleteKnowledgeDocuments(documentIds: number[]) {
  return apiFetch<KnowledgeBatchDeleteResult>("/api/knowledge/documents/delete", {
    method: "POST",
    body: JSON.stringify({ document_ids: documentIds }),
  });
}

export function moveKnowledgeDocuments(documentIds: number[], folder: string) {
  return apiFetch<KnowledgeBatchMoveResult>("/api/knowledge/documents/folder", {
    method: "PATCH",
    body: JSON.stringify({ document_ids: documentIds, folder }),
  });
}
