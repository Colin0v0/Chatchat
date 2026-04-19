import type {
  KnowledgeBatchDeleteResult,
  KnowledgeBatchUploadResult,
  KnowledgeDocument,
  KnowledgeReindexResult,
  KnowledgeStatus,
} from "../../../types";
import { apiFetch, assertApiResponse, toApiUrl } from "../../../shared/api/http";

export function fetchKnowledgeDocuments() {
  return apiFetch<KnowledgeDocument[]>("/api/knowledge/documents");
}

export function fetchKnowledgeStatus() {
  return apiFetch<KnowledgeStatus>("/api/knowledge/status");
}

export async function uploadKnowledgeDocuments(files: File[]) {
  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));

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
