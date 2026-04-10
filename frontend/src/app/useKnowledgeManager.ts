import { useCallback, useEffect, useMemo, useState } from "react";

import {
  deleteKnowledgeDocument,
  deleteKnowledgeDocuments,
  fetchKnowledgeDocuments,
  fetchKnowledgeStatus,
  reindexKnowledgeDocument,
  reindexKnowledgeDocuments,
  uploadKnowledgeDocuments,
} from "../lib/api";
import type { KnowledgeDocument, KnowledgeReindexResult, KnowledgeStatus } from "../types";
import { useLatestRequestGuard } from "./useLatestRequestGuard";

function createEmptyStatus(): KnowledgeStatus {
  return {
    document_count: 0,
    pending_document_count: 0,
    indexing_document_count: 0,
    ready_document_count: 0,
    failed_document_count: 0,
    chunk_count: 0,
    total_size_bytes: 0,
    max_documents_per_user: 0,
    max_total_size_bytes: 0,
    max_file_size_bytes: 0,
  };
}

export function useKnowledgeManager({ open }: { open: boolean }) {
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [status, setStatus] = useState<KnowledgeStatus>(createEmptyStatus);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isUpdating, setIsUpdating] = useState(false);
  const [updateResult, setUpdateResult] = useState<KnowledgeReindexResult | null>(null);
  const [selectedDocumentIds, setSelectedDocumentIds] = useState<number[]>([]);
  const loadGuard = useLatestRequestGuard();

  const loadKnowledge = useCallback(async () => {
    const requestId = loadGuard.begin();
    setIsLoading(true);
    setError(null);
    try {
      const [nextDocuments, nextStatus] = await Promise.all([
        fetchKnowledgeDocuments(),
        fetchKnowledgeStatus(),
      ]);
      if (!loadGuard.isCurrent(requestId)) {
        return;
      }
      setDocuments(nextDocuments);
      setStatus(nextStatus);
      setSelectedDocumentIds((current) =>
        current.filter((documentId) => nextDocuments.some((document) => document.id === documentId)),
      );
    } catch (loadError) {
      if (loadGuard.isCurrent(requestId)) {
        setError(loadError instanceof Error ? loadError.message : "Failed to load knowledge documents.");
      }
    } finally {
      if (loadGuard.isCurrent(requestId)) {
        setIsLoading(false);
      }
    }
  }, [loadGuard]);

  useEffect(() => {
    if (!open) {
      return;
    }
    void loadKnowledge();
  }, [loadKnowledge, open]);

  useEffect(() => {
    if (!open || status.indexing_document_count === 0) {
      return;
    }

    const timer = window.setInterval(() => {
      void loadKnowledge();
    }, 3000);
    return () => window.clearInterval(timer);
  }, [loadKnowledge, open, status.indexing_document_count]);

  const uploadDocuments = useCallback(
    async (files: File[]) => {
      if (files.length === 0) {
        return;
      }
      setIsSaving(true);
      setError(null);
      setUpdateResult(null);
      try {
        await uploadKnowledgeDocuments(files);
        await loadKnowledge();
      } catch (uploadError) {
        setError(uploadError instanceof Error ? uploadError.message : "Failed to upload knowledge documents.");
      } finally {
        setIsSaving(false);
      }
    },
    [loadKnowledge],
  );

  const reindexDocument = useCallback(
    async (documentId: number) => {
      setIsSaving(true);
      setError(null);
      setUpdateResult(null);
      try {
        await reindexKnowledgeDocument(documentId);
        await loadKnowledge();
      } catch (reindexError) {
        setError(reindexError instanceof Error ? reindexError.message : "Failed to reindex knowledge document.");
      } finally {
        setIsSaving(false);
      }
    },
    [loadKnowledge],
  );

  const removeDocument = useCallback(
    async (documentId: number) => {
      setIsSaving(true);
      setError(null);
      setUpdateResult(null);
      try {
        await deleteKnowledgeDocument(documentId);
        await loadKnowledge();
      } catch (deleteError) {
        setError(deleteError instanceof Error ? deleteError.message : "Failed to delete knowledge document.");
      } finally {
        setIsSaving(false);
      }
    },
    [loadKnowledge],
  );

  const removeSelectedDocuments = useCallback(async () => {
    if (selectedDocumentIds.length === 0) {
      return;
    }
    setIsSaving(true);
    setError(null);
    setUpdateResult(null);
    try {
      if (selectedDocumentIds.length === 1) {
        await deleteKnowledgeDocument(selectedDocumentIds[0]);
      } else {
        await deleteKnowledgeDocuments(selectedDocumentIds);
      }
      setSelectedDocumentIds([]);
      await loadKnowledge();
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : "Failed to delete knowledge documents.");
    } finally {
      setIsSaving(false);
    }
  }, [loadKnowledge, selectedDocumentIds]);

  const updateKnowledge = useCallback(async () => {
    setIsUpdating(true);
    setError(null);
    try {
      const result = await reindexKnowledgeDocuments();
      setUpdateResult(result);
      await loadKnowledge();
    } catch (updateError) {
      setError(updateError instanceof Error ? updateError.message : "Failed to update knowledge base.");
    } finally {
      setIsUpdating(false);
    }
  }, [loadKnowledge]);

  return useMemo(
    () => ({
      documents,
      error,
      isLoading,
      isSaving,
      isUpdating: isUpdating || status.indexing_document_count > 0,
      isAllSelected: documents.length > 0 && selectedDocumentIds.length === documents.length,
      onDelete: (documentId: number) => void removeDocument(documentId),
      onDeleteSelected: () => void removeSelectedDocuments(),
      onRefresh: () => void loadKnowledge(),
      onReindex: (documentId: number) => void reindexDocument(documentId),
      onSelectAll: () =>
        setSelectedDocumentIds((current) =>
          current.length === documents.length ? [] : documents.map((document) => document.id),
        ),
      onSelectOne: (documentId: number) =>
        setSelectedDocumentIds((current) =>
          current.includes(documentId)
            ? current.filter((id) => id !== documentId)
            : [...current, documentId],
        ),
      onUpdate: () => void updateKnowledge(),
      onUploadMany: (files: File[]) => void uploadDocuments(files),
      selectedDocumentIds,
      status,
      updateResult,
    }),
    [
      documents,
      error,
      isLoading,
      isSaving,
      isUpdating,
      loadKnowledge,
      removeDocument,
      removeSelectedDocuments,
      reindexDocument,
      selectedDocumentIds,
      status,
      updateKnowledge,
      updateResult,
      uploadDocuments,
    ],
  );
}
